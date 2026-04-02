from __future__ import annotations

from trace_topology.analysis import analyze_graph
from trace_topology.graph import build_graph
from trace_topology.parser import parse_transcript


def test_analyze_returns_stats() -> None:
    steps = parse_transcript("A because B. Therefore C.")
    graph = build_graph(steps, transcript_id="t")
    report = analyze_graph(graph)
    assert "steps" in report.stats
    assert "findings" in report.stats


def test_detects_unsupported_terminal() -> None:
    steps = parse_transcript("Therefore the answer is 42.")
    graph = build_graph(steps, transcript_id="u")
    report = analyze_graph(graph)
    types = {f.type.value for f in report.findings}
    assert "unsupported_terminal" in types
