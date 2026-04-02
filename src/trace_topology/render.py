from __future__ import annotations

from collections import defaultdict

from trace_topology.models import AnalysisReport, BondType, TraceGraph


def _bond_symbol(bond_type: BondType) -> str:
    if bond_type == BondType.COVALENT:
        return "==>"
    if bond_type == BondType.HYDROGEN:
        return "~>"
    return "->"


def render_graph_ascii(graph: TraceGraph) -> str:
    lines = [f"trace: {graph.transcript_id}", ""]
    step_map = {step.id: step for step in graph.steps}
    outgoing: dict[str, list[tuple[str, BondType]]] = defaultdict(list)
    for bond in graph.bonds:
        outgoing[bond.source].append((bond.target, bond.type))

    for step in graph.steps:
        lines.append(f"[{step.id}] {step.summary}")
        for target, btype in outgoing.get(step.id, []):
            target_summary = step_map[target].summary if target in step_map else target
            lines.append(f"  {_bond_symbol(btype)} [{target}] {target_summary}")
    lines.append("")
    lines.append("legend: ==> covalent | ~> hydrogen | -> vanderwaals")
    return "\n".join(lines)


def render_report_ascii(report: AnalysisReport) -> str:
    graph_block = render_graph_ascii(report.graph)
    lines = [graph_block, "", "findings:"]
    if not report.findings:
        lines.append("  - none")
    else:
        for finding in report.findings:
            steps = ",".join(finding.steps_involved) if finding.steps_involved else "-"
            lines.append(
                f"  - {finding.type.value} ({finding.severity}) "
                f"steps={steps}: {finding.description}"
            )
    lines.append("")
    lines.append(f"stats: {report.stats}")
    return "\n".join(lines)
