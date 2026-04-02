from __future__ import annotations

from collections import Counter, defaultdict

from trace_topology.models import AnalysisReport, BondType, Finding, FindingType, TraceGraph


def _adjacency(graph: TraceGraph) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for bond in graph.bonds:
        out[bond.source].append(bond.target)
    return out


def detect_cycles(graph: TraceGraph) -> list[Finding]:
    adj = _adjacency(graph)
    visited: set[str] = set()
    stack: set[str] = set()
    findings: list[Finding] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        stack.add(node)
        for nxt in adj.get(node, []):
            if nxt not in visited:
                dfs(nxt, path + [nxt])
            elif nxt in stack:
                cycle_nodes = path[path.index(nxt) :] if nxt in path else [node, nxt]
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
    for step in graph.steps:
        if incoming[step.id] == 0 and outgoing[step.id] == 0:
            findings.append(
                Finding(
                    type=FindingType.DANGLING,
                    steps_involved=[step.id],
                    description="Reasoning step is disconnected from the graph.",
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
        if outgoing[step.id] == 0 and step.step_type == "conclusion" and incoming[step.id] == 0:
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
            if (
                "not" in a_low
                and "not" not in b_low
                and any(tok in b_low for tok in a_low.replace("not", "").split()[:4])
            ) or (
                "not" in b_low
                and "not" not in a_low
                and any(tok in a_low for tok in b_low.replace("not", "").split()[:4])
            ):
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
    if len(graph.steps) < 4:
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
