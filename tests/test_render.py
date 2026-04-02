from __future__ import annotations

from trace_topology.analysis import analyze_graph
from trace_topology.graph import build_graph
from trace_topology.parser import parse_transcript
from trace_topology.render import render_graph_ascii, render_report_ascii


def test_render_graph_ascii() -> None:
    steps = parse_transcript("A. Therefore B.")
    graph = build_graph(steps, transcript_id="r")
    out = render_graph_ascii(graph)
    assert "legend:" in out
    assert "[s1]" in out


def test_render_report_ascii() -> None:
    steps = parse_transcript("Therefore 42.")
    graph = build_graph(steps, transcript_id="r2")
    report = analyze_graph(graph)
    out = render_report_ascii(report)
    assert "findings:" in out
    assert "stats:" in out
