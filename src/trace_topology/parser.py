from __future__ import annotations

import re

from trace_topology.artifacts import parse_artifact
from trace_topology.models import Step

STEP_SPLIT_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:\d+[\.\)]\s+|[-*]\s+|P\d+\s*:|#{1,6}\s+\S{3,}|<think>|</think>|<thinking>|</thinking>)"
)
TRANSITION_RE = re.compile(
    r"\b(therefore|because|however|but|wait|actually|reconsider|on the other hand|so)\b",
    re.IGNORECASE,
)

TRANSITION_LINE_START_RE = re.compile(
    r"^\s*(therefore|because|however|but|wait|actually|reconsider|on the other hand|so)\b",
    re.IGNORECASE,
)
# List / block markers only (excludes discourse words like "so", "but") for deciding line-split mode.
STRUCTURAL_LINE_RE = re.compile(
    r"^\s*(?:\d+[\.\)]\s+|[-*]\s+|P\d+\s*:|#{1,6}\s+\S{3,}|<redacted_thinking>|</redacted_thinking>|<thinking>|</thinking>)",
    re.IGNORECASE,
)

FENCE_LINE_RE = re.compile(r"(?m)^\s*```[^\n]*$")
THINK_OPEN_RE = re.compile(r"(?i)<(think|thinking)>")


def _find_code_fence_ranges(text: str) -> list[tuple[int, int]]:
    """Return [start,end) ranges for fenced code blocks (``` ... ```)."""
    ranges: list[tuple[int, int]] = []
    lines = text.splitlines()
    cursor = 0
    inside = False
    start: int | None = None
    for raw in lines:
        line_start = cursor
        line_end = cursor + len(raw)
        cursor = line_end + 1
        if not FENCE_LINE_RE.match(raw):
            continue
        if not inside:
            inside = True
            start = line_start
        else:
            inside = False
            if start is not None:
                ranges.append((start, line_end))
            start = None
    if inside and start is not None:
        ranges.append((start, len(text)))
    return ranges


def _find_thinking_ranges(text: str) -> list[tuple[int, int]]:
    """Return [start,end) ranges for <think>/<thinking> blocks."""
    ranges: list[tuple[int, int]] = []
    pos = 0
    while True:
        m = THINK_OPEN_RE.search(text, pos)
        if not m:
            break
        tag = m.group(1).lower()
        open_start = m.start()
        close = f"</{tag}>"
        close_m = re.search(re.escape(close), text[m.end() :], re.IGNORECASE)
        if not close_m:
            break
        close_end = m.end() + close_m.end()
        ranges.append((open_start, close_end))
        pos = close_end
    return ranges


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    ranges = sorted(ranges, key=lambda r: (r[0], r[1]))
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _pos_in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= pos < end:
            return True
    return False


def _range_intersects(a_start: int, a_end: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if a_start < end and a_end > start:
            return True
    return False


def _is_thinking_tag_match(matched_text: str) -> bool:
    low = matched_text.lower()
    return "<think>" in low or "</think>" in low or "<thinking>" in low or "</thinking>" in low
CONCLUSION_RE = re.compile(
    r"\b(therefore|thus|in conclusion|in summary|ultimately|final answer|the answer is|the result is|given everything above)\b|^\s*so,?\s+there\s+(?:are|is)\b",
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
BOXED_RE = re.compile(r"^\s*\\boxed\{.+\}\s*$")
EQUATIONISH_RE = re.compile(
    r"(=|÷|×|\+|\b\d+\s*-\s*\d+\b|\b\d+\s*/\s*\d+\b|\\boxed\{|C\(\d+,\d+\))"
)
SHORT_LEADIN_RE = re.compile(r"^\s*(so|therefore|thus|hence|but remember|in that case)\b", re.IGNORECASE)
RESTATEMENT_TAIL_RE = re.compile(
    r"^\s*(the condition that|this means|in other words|so this means)\b",
    re.IGNORECASE,
)


def _step_type(text: str) -> str:
    low = text.lower()
    if BOXED_RE.match(text):
        return "conclusion"
    if CORRECTION_RE.search(text):
        return "correction"
    if CONCLUSION_RE.search(text):
        return "conclusion"
    if EQUATIONISH_RE.search(text):
        return "derivation"
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
    code_fence_ranges = _find_code_fence_ranges(text)
    thinking_ranges = _find_thinking_ranges(text)
    atomic_ranges = _merge_ranges([*code_fence_ranges, *thinking_ranges])

    lines = text.splitlines()
    if _should_split_lines(lines, atomic_ranges):
        return _split_by_lines(text, lines, atomic_ranges)

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
            in_atomic = _range_intersects(start, end, atomic_ranges)
            if stripped or in_atomic:
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

    # Boundary triggers should never fire inside fenced code blocks.
    # For <think>/<thinking>, we keep splitting at the tags themselves but avoid
    # splitting on list markers / headings inside the block.
    matches = []
    for m in STEP_SPLIT_RE.finditer(text):
        pos = m.start()
        if _pos_in_ranges(pos, code_fence_ranges):
            continue
        if _pos_in_ranges(pos, thinking_ranges) and not _is_thinking_tag_match(m.group(0)):
            continue
        matches.append(m)
    if not matches:
        return _split_by_transitions(text, atomic_ranges)

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
        return _split_by_transitions(text, atomic_ranges)

    refined: list[tuple[int, int, str]] = []
    for start, end, seg in chunks:
        has_line_start_transition = any(
            TRANSITION_LINE_START_RE.search(line) for line in seg.splitlines() if line.strip()
        )
        if "\n" in seg and has_line_start_transition and not _range_intersects(start, end, atomic_ranges):
            for line in seg.splitlines():
                part = line.strip()
                if not part:
                    continue
                p_start = text.find(part, start, end)
                refined.append((p_start, p_start + len(part), part))
        else:
            refined.append((start, end, seg))
    return refined


def _should_split_lines(lines: list[str], atomic_ranges: list[tuple[int, int]]) -> bool:
    """Use one-step-per-line only for list-like traces or dense multi-sentence prose blocks.

    Avoid treating every short line in a multi-paragraph trace (e.g. harvested CoT with blank
    lines) as its own step—that caused severe over-segmentation.
    """
    cursor = 0
    non_empty: list[str] = []
    structural = 0
    has_blank_separator = False
    for raw in lines:
        start = cursor
        end = cursor + len(raw)
        cursor = end + 1

        stripped = raw.strip()
        in_atomic = _range_intersects(start, end, atomic_ranges)
        if not stripped:
            if not in_atomic:
                has_blank_separator = True
            continue

        if in_atomic:
            continue

        non_empty.append(stripped)
        if STRUCTURAL_LINE_RE.search(raw):
            structural += 1
    if len(non_empty) < 2:
        return False
    if structural >= 2:
        return True

    if structural == 0 and not has_blank_separator:
        avg_len = sum(len(s) for s in non_empty) / len(non_empty)
        # Dense prose: e.g. contradiction fixture (long sentences, no list markers).
        # Short average lines without structure stay merged (terse handshake-style blocks).
        if avg_len >= 48:
            return True
    return False


def _split_by_lines(
    text: str, lines: list[str], atomic_ranges: list[tuple[int, int]]
) -> list[tuple[int, int, str]]:
    pieces: list[tuple[int, int, str]] = []
    cursor = 0
    atomic_ranges = sorted(atomic_ranges, key=lambda r: (r[0], r[1]))
    ai = 0
    skip_until = -1
    for raw in lines:
        stripped = raw.strip()
        start = cursor
        end = cursor + len(raw)
        cursor = end + 1

        if start < skip_until:
            continue

        if ai < len(atomic_ranges):
            a_start, a_end = atomic_ranges[ai]
            if start < a_end and end > a_start:
                segment = text[a_start:a_end].strip()
                if segment:
                    true_start = text.find(segment, a_start, a_end)
                    pieces.append((true_start, true_start + len(segment), segment))
                skip_until = a_end
                ai += 1
                continue

        if not stripped:
            continue
        true_start = text.find(stripped, start, end + 1)
        pieces.append((true_start, true_start + len(stripped), stripped))
    return pieces


def _split_by_transitions(text: str, atomic_ranges: list[tuple[int, int]]) -> list[tuple[int, int, str]]:
    pieces: list[tuple[int, int, str]] = []
    starts = [0]
    for m in TRANSITION_RE.finditer(text):
        idx = m.start()
        if idx > 0 and not _pos_in_ranges(idx, atomic_ranges):
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


def _word_count(text: str) -> int:
    return len(text.split())


def _is_equationish(text: str) -> bool:
    return bool(EQUATIONISH_RE.search(text))


def _merge_two_chunks(
    transcript: str,
    left: tuple[int, int, str],
    right: tuple[int, int, str],
) -> tuple[int, int, str]:
    start = left[0]
    end = right[1]
    segment = transcript[start:end].strip()
    true_start = transcript.find(segment, start, end)
    return (true_start, true_start + len(segment), segment)


def _merge_chunks(
    transcript: str, chunks: list[tuple[int, int, str]]
) -> list[tuple[int, int, str]]:
    if len(chunks) < 2:
        return chunks

    merged = list(chunks)

    changed = True
    while changed:
        changed = False
        i = 0
        next_chunks: list[tuple[int, int, str]] = []
        while i < len(merged):
            current = merged[i]
            current_text = current[2]
            next_chunk = merged[i + 1] if i + 1 < len(merged) else None
            prev_chunk = next_chunks[-1] if next_chunks else None

            if next_chunk is not None:
                next_text = next_chunk[2]
                if (
                    current_text.rstrip().endswith(":")
                    and _word_count(current_text) <= 14
                    and (SHORT_LEADIN_RE.search(current_text) or current_text.strip().endswith(":"))
                    and (_is_equationish(next_text) or BOXED_RE.match(next_text))
                ):
                    next_chunks.append(_merge_two_chunks(transcript, current, next_chunk))
                    i += 2
                    changed = True
                    continue

            if (
                prev_chunk is not None
                and next_chunk is not None
                and BOXED_RE.match(next_chunk[2])
                and RESTATEMENT_TAIL_RE.search(current_text)
                and not _is_equationish(current_text)
                and _is_equationish(prev_chunk[2])
            ):
                next_chunks[-1] = _merge_two_chunks(transcript, prev_chunk, current)
                i += 1
                changed = True
                continue

            next_chunks.append(current)
            i += 1
        merged = next_chunks

    return merged


def parse_transcript(transcript: str) -> list[Step]:
    chunks = _merge_chunks(transcript, _split_blocks(transcript))
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
    return parse_artifact(transcript_id, steps, len(transcript))
