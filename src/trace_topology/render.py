from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from trace_topology.models import AnalysisReport, BondType, TraceGraph

COMPACT_RENDER_THRESHOLD = 15
PHASE_WINDOW_SIZE = 6
PHASE_MARKER_RE = re.compile(r"^(#{1,6}\s+.+|\*\*(Claim|Counterclaim|Conclusion)\b.+|\*?\*?Justification:)", re.IGNORECASE)


@dataclass(slots=True)
class _Phase:
    index: int
    step_ids: list[str]
    label: str

    @property
    def phase_id(self) -> str:
        return f"p{self.index}"

    @property
    def start_step(self) -> str:
        return self.step_ids[0]

    @property
    def end_step(self) -> str:
        return self.step_ids[-1]


def _bond_symbol(bond_type: BondType) -> str:
    if bond_type == BondType.COVALENT:
        return "==>"
    if bond_type == BondType.HYDROGEN:
        return "~>"
    return "->"


def _should_render_compact(graph: TraceGraph) -> bool:
    return len(graph.steps) >= COMPACT_RENDER_THRESHOLD


def _clean_label(text: str) -> str:
    clean = text.strip()
    clean = re.sub(r"^#{1,6}\s*", "", clean)
    clean = clean.strip("* ")
    clean = re.sub(r"^(Claim|Counterclaim|Conclusion)\s*\d*\s*:\s*", r"\1: ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^Step\s+\d+\s*:\s*", "", clean, flags=re.IGNORECASE)
    clean = " ".join(clean.split())
    return clean if len(clean) <= 64 else clean[:61].rstrip() + "..."


def _is_phase_marker(step_text: str) -> bool:
    return bool(PHASE_MARKER_RE.match(step_text.strip()))


def _build_phases(graph: TraceGraph) -> list[_Phase]:
    phases: list[list] = []
    current: list = []

    for step in graph.steps:
        if current and _is_phase_marker(step.text):
            phases.append(current)
            current = [step]
        else:
            current.append(step)
    if current:
        phases.append(current)

    expanded: list[list] = []
    for phase_steps in phases:
        if len(phase_steps) <= PHASE_WINDOW_SIZE:
            expanded.append(phase_steps)
            continue
        for i in range(0, len(phase_steps), PHASE_WINDOW_SIZE):
            expanded.append(phase_steps[i : i + PHASE_WINDOW_SIZE])

    built: list[_Phase] = []
    for idx, phase_steps in enumerate(expanded, start=1):
        first = phase_steps[0]
        label = _clean_label(first.text if _is_phase_marker(first.text) else first.summary or first.text)
        built.append(_Phase(index=idx, step_ids=[step.id for step in phase_steps], label=label))
    return built


def _format_summary_line(graph: TraceGraph) -> str:
    counts = Counter(bond.type.value for bond in graph.bonds)
    return (
        "summary: "
        f"steps={len(graph.steps)} bonds={len(graph.bonds)} "
        f"covalent={counts['covalent']} hydrogen={counts['hydrogen']} vanderwaals={counts['vanderwaals']}"
    )


def _phase_connectivity(graph: TraceGraph, phases: list[_Phase]) -> list[str]:
    step_to_phase = {
        step_id: phase.phase_id
        for phase in phases
        for step_id in phase.step_ids
    }
    aggregated: dict[tuple[str, str, BondType], int] = defaultdict(int)
    for bond in graph.bonds:
        source_phase = step_to_phase.get(bond.source)
        target_phase = step_to_phase.get(bond.target)
        if not source_phase or not target_phase or source_phase == target_phase:
            continue
        aggregated[(source_phase, target_phase, bond.type)] += 1

    order = {phase.phase_id: phase.index for phase in phases}
    lines: list[str] = []
    for (source_phase, target_phase, bond_type), count in sorted(
        aggregated.items(),
        key=lambda item: (
            order[item[0][0]],
            order[item[0][1]],
            item[0][2].value,
        ),
    ):
        lines.append(f"  [{source_phase}] {_bond_symbol(bond_type)} [{target_phase}] x{count}")
    return lines


def _compact_graph_lines(graph: TraceGraph) -> list[str]:
    lines = [f"trace: {graph.transcript_id}", _format_summary_line(graph), "", "phases:"]
    phases = _build_phases(graph)
    for phase in phases:
        step_span = phase.start_step if phase.start_step == phase.end_step else f"{phase.start_step}-{phase.end_step}"
        lines.append(f"  [{phase.phase_id}] {step_span} {phase.label} ({len(phase.step_ids)} steps)")

    phase_edges = _phase_connectivity(graph, phases)
    if phase_edges:
        lines.append("")
        lines.append("phase-links:")
        lines.extend(phase_edges)
    return lines


def _compact_graph_block(graph: TraceGraph) -> str:
    lines = _compact_graph_lines(graph)
    lines.extend(["", "hotspots: use `tt analyze` for finding-local neighborhoods", "", "legend: ==> covalent | ~> hydrogen | -> vanderwaals"])
    return "\n".join(lines)


def _full_graph_block(graph: TraceGraph) -> str:
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


def _neighborhood_nodes(report: AnalysisReport, step_ids: list[str]) -> tuple[str, ...]:
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for bond in report.graph.bonds:
        outgoing[bond.source].add(bond.target)
        incoming[bond.target].add(bond.source)

    seen: set[str] = set(step_ids)
    for step_id in list(step_ids):
        seen.update(outgoing.get(step_id, set()))
        seen.update(incoming.get(step_id, set()))

    order = {step.id: idx for idx, step in enumerate(report.graph.steps)}
    return tuple(sorted(seen, key=lambda step_id: order.get(step_id, 0)))


def _render_hotspots(report: AnalysisReport) -> list[str]:
    if not report.findings:
        return ["hotspots: none"]

    step_map = {step.id: step for step in report.graph.steps}
    grouped: dict[tuple[str, ...], list] = defaultdict(list)
    for finding in report.findings:
        grouped[_neighborhood_nodes(report, finding.steps_involved)].append(finding)

    outgoing: dict[str, list] = defaultdict(list)
    for bond in report.graph.bonds:
        outgoing[bond.source].append(bond)

    order = {step.id: idx for idx, step in enumerate(report.graph.steps)}
    lines = ["hotspots:"]
    for hotspot_idx, (nodes, findings) in enumerate(
        sorted(grouped.items(), key=lambda item: min(order.get(step_id, 0) for step_id in item[0])),
        start=1,
    ):
        labels = ", ".join(
            f"{finding.type.value} ({finding.severity}) steps={','.join(finding.steps_involved) if finding.steps_involved else '-'}"
            for finding in findings
        )
        lines.append(f"  [h{hotspot_idx}] {labels}")
        node_set = set(nodes)
        for node_id in nodes:
            step = step_map.get(node_id)
            if step is None:
                continue
            lines.append(f"    [{node_id}] {step.summary}")
            for bond in sorted(
                outgoing.get(node_id, []),
                key=lambda item: (order.get(item.target, 0), item.type.value),
            ):
                if bond.target not in node_set:
                    continue
                target_summary = step_map[bond.target].summary if bond.target in step_map else bond.target
                lines.append(f"      {_bond_symbol(bond.type)} [{bond.target}] {target_summary}")
    return lines


def render_graph_ascii(graph: TraceGraph) -> str:
    if _should_render_compact(graph):
        return _compact_graph_block(graph)
    return _full_graph_block(graph)


def render_report_ascii(report: AnalysisReport) -> str:
    if not _should_render_compact(report.graph):
        graph_block = _full_graph_block(report.graph)
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

    lines = _compact_graph_lines(report.graph)
    lines.append("")
    lines.extend(_render_hotspots(report))
    lines.append("")
    lines.append("legend: ==> covalent | ~> hydrogen | -> vanderwaals")
    lines.append("")
    lines.append(f"stats: {report.stats}")
    return "\n".join(lines)
