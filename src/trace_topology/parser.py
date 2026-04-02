from __future__ import annotations

import re
from dataclasses import asdict

from trace_topology.models import Step

STEP_SPLIT_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:\d+[\.\)]\s+|[-*]\s+|P\d+\s*:|<think>|</think>|<thinking>|</thinking>)"
)
TRANSITION_RE = re.compile(
    r"\b(therefore|because|however|but|wait|actually|reconsider|on the other hand|so)\b",
    re.IGNORECASE,
)
# List / block markers only (excludes discourse words like "so", "but") for deciding line-split mode.
STRUCTURAL_LINE_RE = re.compile(
    r"^\s*(?:\d+[\.\)]\s+|[-*]\s+|P\d+\s*:|<redacted_thinking>|</redacted_thinking>|<thinking>|</thinking>)",
    re.IGNORECASE,
)
CONCLUSION_RE = re.compile(
    r"\b(therefore|thus|in conclusion|ultimately|final answer|the answer is|the result is|given everything above)\b",
    re.IGNORECASE,
)
CORRECTION_RE = re.compile(
    r"\b(wait|reconsider|i was wrong|that was wrong|correction|mistake|ignored|ignore)\b",
    re.IGNORECASE,
)
EXPLORATION_RE = re.compile(r"\b(maybe|perhaps|could|might|another angle|alternatively)\b", re.IGNORECASE)
DERIVATION_RE = re.compile(
    r"\b(because|given|hence|since|which means|this means)\b|^\s*then\b|^\s*actually i should\b",
    re.IGNORECASE,
)


def _step_type(text: str) -> str:
    low = text.lower()
    if CORRECTION_RE.search(text):
        return "correction"
    if CONCLUSION_RE.search(text):
        return "conclusion"
    if EXPLORATION_RE.search(text):
        return "exploration"
    if DERIVATION_RE.search(text):
        return "derivation"
    if "?" in text:
        return "question"
    if low.startswith("actually "):
        return "derivation"
    return "claim"


def _summarize(text: str, max_len: int = 120) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3].rstrip() + "..."


def _split_blocks(text: str) -> list[tuple[int, int, str]]:
    chunks: list[tuple[int, int, str]] = []
    if not text.strip():
        return chunks

    lines = text.splitlines()
    if _should_split_lines(lines):
        return _split_by_lines(text, lines)

    # For long markdown-ish traces, paragraph boundaries are usually better
    # than splitting on every line wrap.
    if len(lines) >= 3:
        line_chunks = []
        cursor = 0
        para_start: int | None = None
        para_end = 0
        for raw in lines:
            stripped = raw.strip()
            start = cursor
            end = cursor + len(raw)
            cursor = end + 1
            if stripped:
                if para_start is None:
                    para_start = start
                para_end = end
                continue
            if para_start is not None:
                segment = text[para_start:para_end].strip()
                if segment:
                    true_start = text.find(segment, para_start, para_end + 1)
                    line_chunks.append((true_start, true_start + len(segment), segment))
                para_start = None
        if para_start is not None:
            segment = text[para_start:para_end].strip()
            if segment:
                true_start = text.find(segment, para_start, para_end + 1)
                line_chunks.append((true_start, true_start + len(segment), segment))

        if len(line_chunks) >= 2:
            return line_chunks

    matches = list(STEP_SPLIT_RE.finditer(text))
    if not matches:
        return _split_by_transitions(text)

    boundaries = [0]
    for m in matches:
        boundaries.append(m.start())
    boundaries.append(len(text))

    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        segment = text[start:end].strip()
        if not segment:
            continue
        true_start = text.find(segment, start, end)
        true_end = true_start + len(segment)
        chunks.append((true_start, true_end, segment))
    if not chunks:
        return _split_by_transitions(text)

    refined: list[tuple[int, int, str]] = []
    for start, end, seg in chunks:
        if "\n" in seg and TRANSITION_RE.search(seg):
            for line in seg.splitlines():
                part = line.strip()
                if not part:
                    continue
                p_start = text.find(part, start, end)
                refined.append((p_start, p_start + len(part), part))
        else:
            refined.append((start, end, seg))
    return refined


def _has_blank_line_separator(lines: list[str]) -> bool:
    return any(not raw.strip() for raw in lines)


def _should_split_lines(lines: list[str]) -> bool:
    """Use one-step-per-line only for list-like traces or dense multi-sentence prose blocks.

    Avoid treating every short line in a multi-paragraph trace (e.g. harvested CoT with blank
    lines) as its own step—that caused severe over-segmentation.
    """
    non_empty = [line.strip() for line in lines if line.strip()]
    if len(non_empty) < 2:
        return False
    structural = sum(1 for line in non_empty if STRUCTURAL_LINE_RE.search(line))
    if structural >= 2:
        return True
    if structural == 0 and not _has_blank_line_separator(lines):
        avg_len = sum(len(s) for s in non_empty) / len(non_empty)
        # Dense prose: e.g. contradiction fixture (long sentences, no list markers).
        # Short average lines without structure stay merged (terse handshake-style blocks).
        if avg_len >= 48:
            return True
    return False


def _split_by_lines(text: str, lines: list[str]) -> list[tuple[int, int, str]]:
    pieces: list[tuple[int, int, str]] = []
    cursor = 0
    for raw in lines:
        stripped = raw.strip()
        start = cursor
        end = cursor + len(raw)
        cursor = end + 1
        if not stripped:
            continue
        true_start = text.find(stripped, start, end + 1)
        pieces.append((true_start, true_start + len(stripped), stripped))
    return pieces


def _split_by_transitions(text: str) -> list[tuple[int, int, str]]:
    pieces: list[tuple[int, int, str]] = []
    starts = [0]
    for m in TRANSITION_RE.finditer(text):
        idx = m.start()
        if idx > 0:
            starts.append(idx)
    starts.append(len(text))

    for i in range(len(starts) - 1):
        start, end = starts[i], starts[i + 1]
        frag = text[start:end].strip()
        if not frag:
            continue
        true_start = text.find(frag, start, end)
        true_end = true_start + len(frag)
        pieces.append((true_start, true_end, frag))
    if pieces:
        return pieces

    clean = text.strip()
    start = text.find(clean)
    return [(start, start + len(clean), clean)] if clean else []


def parse_transcript(transcript: str) -> list[Step]:
    chunks = _split_blocks(transcript)
    steps: list[Step] = []
    for idx, (start, end, segment) in enumerate(chunks, start=1):
        step = Step(
            id=f"s{idx}",
            text=segment,
            start_char=start,
            end_char=end,
            step_type=_step_type(segment),
            summary=_summarize(segment),
        )
        steps.append(step)
    return steps


def parse_to_artifact(transcript: str, transcript_id: str = "stdin") -> dict:
    steps = parse_transcript(transcript)
    return {
        "transcript_id": transcript_id,
        "steps": [asdict(step) for step in steps],
        "stats": {"step_count": len(steps), "char_count": len(transcript)},
    }
