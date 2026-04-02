from __future__ import annotations

import re
from collections import Counter

from trace_topology.backends import BondBackend
from trace_topology.models import Bond, BondType, Step, TraceGraph

LOGICAL_RE = re.compile(r"\b(therefore|thus|because|given|hence|implies|so)\b", re.IGNORECASE)
REFLECT_RE = re.compile(r"\b(wait|actually|reconsider|i was wrong|let me correct)\b", re.IGNORECASE)
LOOSE_RE = re.compile(r"\b(maybe|perhaps|another angle|alternatively|also)\b", re.IGNORECASE)
REF_BACK_RE = re.compile(r"\b(above|earlier|previous|as noted|as said)\b", re.IGNORECASE)
CLAIM_RE = re.compile(r"^\s*(\*\*)?claim\b", re.IGNORECASE)
JUST_RE = re.compile(r"^\s*justification\b", re.IGNORECASE)
LIST_RE = re.compile(r"^\s*(\d+[\.\)]|[-*])\s+")
CONCLUSION_RE = re.compile(r"\b(therefore|in conclusion|ultimately|thus|so)\b", re.IGNORECASE)
POINT_LABEL_RE = re.compile(r"^\s*P(\d+)\s*:", re.IGNORECASE)
POINT_REF_RE = re.compile(r"\bP(\d+)\b")
TOKEN_RE = re.compile(r"[a-z]{4,}")
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


def heuristic_bond_type(source_text: str, target_text: str) -> tuple[BondType, float, str]:
    target = target_text.lower()
    if REFLECT_RE.search(target):
        return BondType.HYDROGEN, 0.8, "reflection-marker"
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
) -> TraceGraph:
    graph = TraceGraph(transcript_id=transcript_id, steps=steps, metadata={})
    if not steps:
        return graph

    bonds: list[Bond] = []
    tokens_by_step = {step.id: _token_set(step.text) for step in steps}
    label_to_step: dict[str, Step] = {}
    for step in steps:
        m = POINT_LABEL_RE.search(step.text)
        if m:
            label_to_step[m.group(1)] = step
    last_claim_id: str | None = None
    last_justification_id: str | None = None
    for i in range(1, len(steps)):
        source = steps[i - 1]
        target = steps[i]
        btype, conf, reason = heuristic_bond_type(source.text, target.text)
        add_adjacency = not (backend is None and reason == "default")
        if backend is not None:
            try:
                result = backend.classify(source.text, target.text)
                btype = BondType(result.bond_type)
                conf = max(conf, result.confidence)
                reason = result.reason
                add_adjacency = True
            except Exception:
                pass
        if add_adjacency:
            bonds.append(
                Bond(
                    source=source.id,
                    target=target.id,
                    type=btype,
                    confidence=conf,
                    reason=reason,
                )
            )

        if CLAIM_RE.search(source.text):
            last_claim_id = source.id
        if JUST_RE.search(source.text):
            last_justification_id = source.id

        if JUST_RE.search(target.text) and CLAIM_RE.search(source.text):
            bonds.append(
                Bond(
                    source=source.id,
                    target=target.id,
                    type=BondType.COVALENT,
                    confidence=0.75,
                    reason="claim-justification",
                )
            )
        elif LIST_RE.search(target.text) and last_justification_id:
            bonds.append(
                Bond(
                    source=last_justification_id,
                    target=target.id,
                    type=BondType.COVALENT,
                    confidence=0.7,
                    reason="justification-item",
                )
            )
        # Claim heading is often followed by a supporting paragraph that lacks
        # explicit discourse markers; connect that structure directly.
        if CLAIM_RE.search(source.text) and not CLAIM_RE.search(target.text):
            bonds.append(
                Bond(
                    source=source.id,
                    target=target.id,
                    type=BondType.COVALENT,
                    confidence=0.65,
                    reason="claim-body",
                )
            )

        # Add non-adjacent support links for conclusion-style statements by
        # choosing the strongest earlier thematic overlap.
        if CONCLUSION_RE.search(target.text) and i >= 2:
            t_tokens = tokens_by_step[target.id]
            best_src: Step | None = None
            best_score = 0.0
            for prior in steps[: i - 1]:
                score = _jaccard(tokens_by_step[prior.id], t_tokens)
                if score > best_score:
                    best_src = prior
                    best_score = score
            if best_src and best_score >= 0.18:
                bonds.append(
                    Bond(
                        source=best_src.id,
                        target=target.id,
                        type=BondType.COVALENT,
                        confidence=min(0.85, 0.5 + best_score),
                        reason="thematic-support",
                    )
                )

    for i, step in enumerate(steps):
        if i < 2:
            continue
        if REF_BACK_RE.search(step.text):
            anchor = steps[max(0, i - 2)]
            bonds.append(
                Bond(
                    source=anchor.id,
                    target=step.id,
                    type=BondType.HYDROGEN,
                    confidence=0.7,
                    reason="back-reference",
                )
            )

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
            bonds.append(
                Bond(
                    source=step.id,
                    target=target_step.id,
                    type=BondType.COVALENT,
                    confidence=0.85,
                    reason="explicit-point-reference",
                )
            )

    # For labeled point chains, keep a weak progression spine. Combined with
    # explicit back-references this can surface closed loops.
    labeled_chain = sorted(
        ((int(k), v) for k, v in label_to_step.items()),
        key=lambda x: x[0],
    )
    for (n1, s1), (n2, s2) in zip(labeled_chain, labeled_chain[1:]):
        if n2 == n1 + 1:
            bonds.append(
                Bond(
                    source=s1.id,
                    target=s2.id,
                    type=BondType.VANDERWAALS,
                    confidence=0.55,
                    reason="point-sequence",
                )
            )

    unique = {(b.source, b.target, b.type.value): b for b in bonds}
    graph.bonds = list(unique.values())
    counts = Counter(b.type.value for b in graph.bonds)
    graph.metadata["bond_counts"] = dict(counts)
    return graph
