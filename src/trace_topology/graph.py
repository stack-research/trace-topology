from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

from trace_topology.models import Bond, BondType, Step, TraceGraph

if TYPE_CHECKING:
    from trace_topology.backends import BondBackend

LOGICAL_RE = re.compile(r"\b(therefore|thus|because|given|hence|implies|so)\b", re.IGNORECASE)
REFLECT_RE = re.compile(r"\b(wait|actually|reconsider|i was wrong|let me correct)\b", re.IGNORECASE)
LOOSE_RE = re.compile(r"\b(maybe|perhaps|another angle|alternatively|also)\b", re.IGNORECASE)
REF_BACK_RE = re.compile(r"\b(above|earlier|previous|as noted|as said)\b", re.IGNORECASE)
CLAIM_RE = re.compile(r"^\s*(\*\*)?claim\b", re.IGNORECASE)
JUST_RE = re.compile(r"^\s*justification\b", re.IGNORECASE)
LIST_RE = re.compile(r"^\s*(\d+[\.\)]|[-*])\s+")
CONCLUSION_RE = re.compile(r"\b(therefore|in conclusion|in summary|ultimately|thus|so)\b", re.IGNORECASE)
POINT_LABEL_RE = re.compile(r"^\s*P(\d+)\s*:", re.IGNORECASE)
POINT_REF_RE = re.compile(r"\bP(\d+)\b")
TOKEN_RE = re.compile(r"[a-z]{4,}")
NUMBER_RE = re.compile(r"\d+")
PROGRESSION_RE = re.compile(r"^\s*(first|next|then|now|so)\b", re.IGNORECASE)
VERIFICATION_RE = re.compile(
    r"\b(consistent with|alternative approach|cross-check|also confirms|confirms this|degree sum approach|check by)\b",
    re.IGNORECASE,
)
INTRO_RE = re.compile(r"^\s*(let's|i should|we should|i will|now, let's)\b", re.IGNORECASE)
STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "been",
    "they",
    "their",
    "which",
    "into",
    "about",
    "while",
    "where",
    "there",
    "these",
    "those",
    "models",
    "model",
}


def _token_set(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(text))


def _word_count(text: str) -> int:
    return len(text.split())


def _is_conclusion_step(step: Step) -> bool:
    if _is_verification_step(step):
        return False
    return step.step_type == "conclusion" or bool(CONCLUSION_RE.search(step.text))


def _is_verification_step(step: Step) -> bool:
    return bool(VERIFICATION_RE.search(step.text))


def _is_intro_step(step: Step) -> bool:
    text = step.text.lower()
    return (
        _word_count(step.text) <= 10
        and bool(INTRO_RE.search(step.text))
        and not LOGICAL_RE.search(text)
        and "because" not in text
    )


def _is_short_result_step(step: Step) -> bool:
    text = step.text.strip()
    if text.startswith("\\boxed{"):
        return True
    if "=" in text and _word_count(text) <= 12:
        return True
    return _word_count(text) <= 8 and bool(_numbers(text))


def _has_numeric_content(step: Step) -> bool:
    return bool(_numbers(step.text))


def _shared_tokens(source: Step, target: Step, tokens_by_step: dict[str, set[str]]) -> set[str]:
    return tokens_by_step[source.id] & tokens_by_step[target.id]


def _support_score(source: Step, target: Step, tokens_by_step: dict[str, set[str]]) -> float:
    score = _jaccard(tokens_by_step[source.id], tokens_by_step[target.id])
    shared_numbers = _numbers(source.text) & _numbers(target.text)
    if shared_numbers:
        score += 0.12 * min(2, len(shared_numbers))
    return score


def _append_bond(
    bonds: list[Bond],
    source: Step,
    target: Step,
    btype: BondType,
    confidence: float,
    reason: str,
) -> None:
    bonds.append(
        Bond(
            source=source.id,
            target=target.id,
            type=btype,
            confidence=confidence,
            reason=reason,
        )
    )


def heuristic_bond_type(source_text: str, target_text: str) -> tuple[BondType, float, str]:
    target = target_text.lower()
    if REFLECT_RE.search(target):
        return BondType.HYDROGEN, 0.8, "reflection-marker"
    if VERIFICATION_RE.search(target):
        return BondType.VANDERWAALS, 0.72, "verification-marker"
    if LOGICAL_RE.search(target):
        return BondType.COVALENT, 0.8, "logical-marker"
    if LOOSE_RE.search(target):
        return BondType.VANDERWAALS, 0.6, "exploration-marker"
    if source_text and target_text and source_text[:20].lower() in target.lower():
        return BondType.COVALENT, 0.7, "text-overlap"
    return BondType.VANDERWAALS, 0.4, "default"


def build_graph(
    steps: list[Step],
    transcript_id: str = "stdin",
    backend: BondBackend | None = None,
    parser_granularity: str = "heuristic",
) -> TraceGraph:
    graph = TraceGraph(
        transcript_id=transcript_id,
        steps=steps,
        metadata={"parser_granularity": parser_granularity},
    )
    if not steps:
        return graph

    bonds: list[Bond] = []
    tokens_by_step = {step.id: _token_set(step.text) for step in steps}
    label_to_step: dict[str, Step] = {}
    for step in steps:
        m = POINT_LABEL_RE.search(step.text)
        if m:
            label_to_step[m.group(1)] = step
    last_conclusion_index = -1
    last_justification_id: str | None = None
    for i in range(1, len(steps)):
        source = steps[i - 1]
        target = steps[i]
        btype, conf, reason = heuristic_bond_type(source.text, target.text)
        add_adjacency = not (backend is None and reason == "default")
        if reason == "default":
            support = _support_score(source, target, tokens_by_step)
            if (
                PROGRESSION_RE.search(target.text)
                or source.text.rstrip().endswith(":")
                or _is_short_result_step(target)
            ):
                btype, conf, reason = BondType.COVALENT, 0.72, "structural-continuation"
                add_adjacency = True
            elif support >= 0.14:
                btype = BondType.COVALENT if target.step_type in {"derivation", "conclusion"} else BondType.VANDERWAALS
                conf = min(0.82, 0.5 + support)
                reason = "thematic-adjacency"
                add_adjacency = True
        if backend is not None:
            result = backend.classify(source.text, target.text)
            try:
                btype = BondType(result.bond_type)
            except ValueError:
                pass
            else:
                conf = max(conf, result.confidence)
                reason = result.reason
                add_adjacency = True
        if _is_verification_step(target):
            last_conclusion = steps[last_conclusion_index] if last_conclusion_index >= 0 else None
            if last_conclusion is not None and source.id != last_conclusion.id:
                add_adjacency = False
        if add_adjacency:
            _append_bond(bonds, source, target, btype, conf, reason)

        if JUST_RE.search(source.text):
            last_justification_id = source.id

        if JUST_RE.search(target.text) and CLAIM_RE.search(source.text):
            _append_bond(bonds, source, target, BondType.COVALENT, 0.75, "claim-justification")
        elif LIST_RE.search(target.text) and last_justification_id:
            just_source = next((step for step in steps if step.id == last_justification_id), None)
            if just_source is not None:
                _append_bond(bonds, just_source, target, BondType.COVALENT, 0.7, "justification-item")
        # Claim heading is often followed by a supporting paragraph that lacks
        # explicit discourse markers; connect that structure directly.
        if CLAIM_RE.search(source.text) and not CLAIM_RE.search(target.text):
            _append_bond(bonds, source, target, BondType.COVALENT, 0.65, "claim-body")

        segment_start = last_conclusion_index + 1
        priors = [step for step in steps[segment_start:i] if not _is_intro_step(step)]

        if _is_verification_step(target):
            conclusion = next(
                (step for step in reversed(steps[:i]) if _is_conclusion_step(step)),
                None,
            )
            if conclusion is not None:
                _append_bond(bonds, conclusion, target, BondType.VANDERWAALS, 0.74, "verification-branch")
        elif _is_conclusion_step(target):
            support_priors = [
                step
                for step in reversed(priors)
                if not _is_short_result_step(step) and not _is_verification_step(step)
            ][:2]
            for prior in reversed(support_priors):
                _append_bond(bonds, prior, target, BondType.COVALENT, 0.76, "local-conclusion-support")

            if not _has_numeric_content(target):
                thematic_priors = [
                    (prior, _support_score(prior, target, tokens_by_step))
                    for prior in priors
                    if prior.id not in {step.id for step in support_priors}
                    and not _is_intro_step(prior)
                    and not _has_numeric_content(prior)
                    and len(_shared_tokens(prior, target, tokens_by_step)) >= 2
                ]
                thematic_priors.sort(key=lambda item: item[1], reverse=True)
                if thematic_priors and thematic_priors[0][1] >= 0.09:
                    prior, score = thematic_priors[0]
                    _append_bond(
                        bonds,
                        prior,
                        target,
                        BondType.COVALENT,
                        min(0.82, 0.55 + score),
                        "thematic-conclusion-support",
                    )

            # Short conclusions that restate an earlier premise can close a loop.
            echoed_candidates = [
                (step, _support_score(step, target, tokens_by_step))
                for step in steps[:i - 1]
                if not _has_numeric_content(step)
                and not _has_numeric_content(target)
                and len(_shared_tokens(step, target, tokens_by_step)) >= 2
            ]
            echoed_prior = None
            if echoed_candidates:
                echoed_prior, echoed_score = max(echoed_candidates, key=lambda item: item[1])
                if echoed_score < 0.09:
                    echoed_prior = None
            if echoed_prior is not None:
                _append_bond(
                    bonds,
                    echoed_prior,
                    target,
                    BondType.COVALENT,
                    0.75,
                    "restated-conclusion-support",
                )
                _append_bond(bonds, target, echoed_prior, BondType.COVALENT, 0.73, "restated-premise")
        else:
            best_src: Step | None = None
            best_score = 0.0
            for prior in priors[:-1]:
                if _is_intro_step(prior):
                    continue
                score = _support_score(prior, target, tokens_by_step)
                if score > best_score:
                    best_src = prior
                    best_score = score
            if best_src is not None and best_score >= 0.18:
                _append_bond(bonds, best_src, target, BondType.COVALENT, min(0.84, 0.52 + best_score), "thematic-support")

        if _is_short_result_step(target):
            numeric_src = next(
                (
                    step
                    for step in reversed(steps[segment_start:i])
                    if step.id != source.id
                    and not _is_intro_step(step)
                    and (
                        _numbers(step.text) & _numbers(target.text)
                        or _is_conclusion_step(step)
                        or step.step_type == "derivation"
                    )
                ),
                None,
            )
            if numeric_src is not None:
                _append_bond(bonds, numeric_src, target, BondType.COVALENT, 0.78, "result-support")

        if _is_conclusion_step(source):
            last_conclusion_index = i - 1
        if _is_conclusion_step(target):
            last_conclusion_index = i

    for i, step in enumerate(steps):
        if i < 2:
            continue
        if REF_BACK_RE.search(step.text):
            anchor = steps[max(0, i - 2)]
            _append_bond(bonds, anchor, step, BondType.HYDROGEN, 0.7, "back-reference")

    # Explicit Pn references are strong structural signals in cycle prompts.
    for step in steps:
        own_label_match = POINT_LABEL_RE.search(step.text)
        own_label = own_label_match.group(1) if own_label_match else None
        seen_refs: set[str] = set()
        for ref in POINT_REF_RE.findall(step.text):
            if ref == own_label or ref in seen_refs:
                continue
            seen_refs.add(ref)
            target_step = label_to_step.get(ref)
            if not target_step:
                continue
            _append_bond(bonds, step, target_step, BondType.COVALENT, 0.85, "explicit-point-reference")

    # For labeled point chains, keep a weak progression spine. Combined with
    # explicit back-references this can surface closed loops.
    labeled_chain = sorted(
        ((int(k), v) for k, v in label_to_step.items()),
        key=lambda x: x[0],
    )
    for (n1, s1), (n2, s2) in zip(labeled_chain, labeled_chain[1:]):
        if n2 == n1 + 1:
            _append_bond(bonds, s1, s2, BondType.VANDERWAALS, 0.55, "point-sequence")

    unique: dict[tuple[str, str, str], Bond] = {}
    for bond in bonds:
        key = (bond.source, bond.target, bond.type.value)
        prior = unique.get(key)
        if prior is None or bond.confidence >= prior.confidence:
            unique[key] = bond
    graph.bonds = list(unique.values())
    counts = Counter(b.type.value for b in graph.bonds)
    graph.metadata["bond_counts"] = dict(counts)
    return graph
