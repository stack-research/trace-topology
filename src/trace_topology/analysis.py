from __future__ import annotations

import re
from collections import Counter, defaultdict

from trace_topology.models import AnalysisReport, BondType, Finding, FindingType, TraceGraph

CONCLUSION_RE = re.compile(
    r"\b(therefore|thus|in conclusion|ultimately|final answer|the answer is|the result is|given everything above)\b",
    re.IGNORECASE,
)
SHIFT_RE = re.compile(r"\b(move on|for now|set that aside|leave that)\b", re.IGNORECASE)
ABANDON_RE = re.compile(
    r"\b(cannot finish|can't finish|cannot prove|can't prove|stuck|cannot complete|can't complete)\b",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-z]{3,}")
STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "they",
    "them",
    "their",
    "there",
    "same",
    "must",
    "should",
    "would",
    "could",
    "into",
    "every",
    "fully",
}
NEGATION_WORDS = {"not", "never", "no", "without", "none", "cannot", "can't"}
ANTONYM_MAP = {
    "visible": "invisible",
    "invisible": "visible",
    "expose": "hidden",
    "hidden": "expose",
    "public": "private",
    "private": "public",
    "transparent": "hidden",
    "safe": "unsafe",
    "unsafe": "safe",
    "allow": "forbid",
    "forbid": "allow",
}


def _adjacency(graph: TraceGraph) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for bond in graph.bonds:
        out[bond.source].append(bond.target)
    return out


def _text_tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}


def _is_conclusion(step_text: str, step_type: str) -> bool:
    return step_type == "conclusion" or bool(CONCLUSION_RE.search(step_text))


def detect_cycles(graph: TraceGraph) -> list[Finding]:
    adj = _adjacency(graph)
    visited: set[str] = set()
    stack: set[str] = set()
    findings: list[Finding] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        stack.add(node)
        for nxt in adj.get(node, []):
            if nxt not in visited:
                dfs(nxt, path + [nxt])
            elif nxt in stack:
                cycle_nodes = path[path.index(nxt) :] if nxt in path else [node, nxt]
                canonical = tuple(sorted(set(cycle_nodes)))
                if canonical in seen_cycles:
                    continue
                seen_cycles.add(canonical)
                findings.append(
                    Finding(
                        type=FindingType.CYCLE,
                        steps_involved=cycle_nodes,
                        description="Cycle detected in support graph.",
                        severity="severe",
                        score=0.9,
                    )
                )
        stack.remove(node)

    for step in graph.steps:
        if step.id not in visited:
            dfs(step.id, [step.id])
    return findings


def detect_dangling_nodes(graph: TraceGraph) -> list[Finding]:
    incoming = Counter(b.target for b in graph.bonds)
    outgoing = Counter(b.source for b in graph.bonds)
    findings: list[Finding] = []
    flagged: set[str] = set()
    for idx, step in enumerate(graph.steps):
        step_low = step.text.lower()
        is_conclusion = _is_conclusion(step.text, step.step_type)
        next_step = graph.steps[idx + 1] if idx + 1 < len(graph.steps) else None

        if (
            outgoing[step.id] == 0
            and incoming[step.id] > 0
            and next_step is not None
            and (
                ABANDON_RE.search(step_low)
                or SHIFT_RE.search(next_step.text.lower())
                or step.step_type in {"exploration", "correction"}
            )
            and not is_conclusion
        ):
            flagged.add(step.id)

        is_isolated = incoming[step.id] == 0 and outgoing[step.id] == 0
        if not is_isolated or is_conclusion or SHIFT_RE.search(step_low):
            continue
        if len(graph.steps) == 1 or 0 < idx < len(graph.steps) - 1:
            flagged.add(step.id)

    for step in graph.steps:
        if step.id in flagged:
            findings.append(
                Finding(
                    type=FindingType.DANGLING,
                    steps_involved=[step.id],
                    description="Reasoning branch is abandoned before it reconnects.",
                    severity="moderate",
                    score=0.7,
                )
            )
    return findings


def detect_unsupported_terminals(graph: TraceGraph) -> list[Finding]:
    incoming = Counter(b.target for b in graph.bonds)
    outgoing = Counter(b.source for b in graph.bonds)
    findings: list[Finding] = []
    for step in graph.steps:
        if outgoing[step.id] == 0 and _is_conclusion(step.text, step.step_type) and incoming[step.id] == 0:
            findings.append(
                Finding(
                    type=FindingType.UNSUPPORTED_TERMINAL,
                    steps_involved=[step.id],
                    description="Conclusion appears without traced support.",
                    severity="severe",
                    score=0.85,
                )
            )
    return findings


def detect_contradictions(graph: TraceGraph) -> list[Finding]:
    findings: list[Finding] = []
    for i, a in enumerate(graph.steps):
        for b in graph.steps[i + 1 :]:
            a_low = a.text.lower()
            b_low = b.text.lower()
            a_tokens = _text_tokens(a_low)
            b_tokens = _text_tokens(b_low)
            shared = a_tokens & b_tokens
            negated = (
                bool(NEGATION_WORDS & set(a_low.split())) != bool(NEGATION_WORDS & set(b_low.split()))
                and len(shared) >= 2
            )
            antonym = any(
                antonym in b_tokens
                for token in a_tokens
                if (antonym := ANTONYM_MAP.get(token)) is not None
            ) and len(shared) >= 1
            if negated or antonym:
                findings.append(
                    Finding(
                        type=FindingType.CONTRADICTION,
                        steps_involved=[a.id, b.id],
                        description="Potential contradiction pair found.",
                        severity="moderate",
                        score=0.6,
                    )
                )
    return findings


def detect_entropy_divergence(graph: TraceGraph) -> list[Finding]:
    if len(graph.steps) < 3:
        return []
    lens = [len(step.text.split()) for step in graph.steps]
    first = sum(lens[: len(lens) // 2]) / max(1, len(lens) // 2)
    second = sum(lens[len(lens) // 2 :]) / max(1, len(lens) - len(lens) // 2)
    if second > first * 1.35:
        return [
            Finding(
                type=FindingType.ENTROPY_DIVERGENCE,
                steps_involved=[graph.steps[-1].id],
                description="Later reasoning gets broader/longer than early focus.",
                severity="moderate",
                score=0.65,
            )
        ]
    return []


def detect_bond_imbalance(graph: TraceGraph) -> list[Finding]:
    if not graph.bonds:
        return []
    counts = Counter(b.type for b in graph.bonds)
    total = sum(counts.values())
    hydrogen_ratio = counts[BondType.HYDROGEN] / total
    covalent_ratio = counts[BondType.COVALENT] / total
    if hydrogen_ratio >= 0.75 and covalent_ratio <= 0.15:
        return [
            Finding(
                type=FindingType.BOND_IMBALANCE,
                steps_involved=[],
                description="Reflection dominates without deep reasoning links.",
                severity="moderate",
                score=0.7,
            )
        ]
    if counts[BondType.VANDERWAALS] / total >= 0.75:
        return [
            Finding(
                type=FindingType.BOND_IMBALANCE,
                steps_involved=[],
                description="Exploration dominates without convergence.",
                severity="moderate",
                score=0.7,
            )
        ]
    return []


def analyze_graph(graph: TraceGraph) -> AnalysisReport:
    findings: list[Finding] = []
    findings.extend(detect_cycles(graph))
    findings.extend(detect_dangling_nodes(graph))
    findings.extend(detect_unsupported_terminals(graph))
    findings.extend(detect_contradictions(graph))
    findings.extend(detect_entropy_divergence(graph))
    findings.extend(detect_bond_imbalance(graph))
    stats = {
        "steps": len(graph.steps),
        "bonds": len(graph.bonds),
        "findings": len(findings),
        "by_type": dict(Counter(f.type.value for f in findings)),
    }
    return AnalysisReport(graph=graph, findings=findings, stats=stats)
