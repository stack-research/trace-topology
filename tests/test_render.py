from __future__ import annotations

from pathlib import Path

from trace_topology.analysis import analyze_graph
from trace_topology.graph import build_graph
from trace_topology.parser import parse_transcript
from trace_topology.render import render_graph_ascii, render_report_ascii


def test_render_graph_ascii_small_trace_keeps_full_layout() -> None:
    steps = parse_transcript("A because B. Therefore C.")
    graph = build_graph(steps, transcript_id="r")
    out = render_graph_ascii(graph)
    assert "legend:" in out
    assert "[s1]" in out
    assert "phases:" not in out


def test_render_report_ascii_small_trace_keeps_findings_block() -> None:
    steps = parse_transcript("Therefore 42.")
    graph = build_graph(steps, transcript_id="r2")
    report = analyze_graph(graph)
    out = render_report_ascii(report)
    assert "findings:" in out
    assert "stats:" in out
    assert "hotspots:" not in out


def test_render_graph_ascii_large_trace_switches_to_compact_layout(samples_dir: Path) -> None:
    transcript = (samples_dir / "llama3.1-8b_circular_trust_20260402.txt").read_text(
        encoding="utf-8"
    )
    graph = build_graph(parse_transcript(transcript), transcript_id="large")
    out = render_graph_ascii(graph)

    assert "summary:" in out
    assert "phases:" in out
    assert "phase-links:" in out
    assert "hotspots: use `tt analyze`" in out
    assert "[p1]" in out
    assert "[s1]" not in out


def test_render_report_ascii_large_trace_includes_hotspots(samples_dir: Path) -> None:
    transcript = (samples_dir / "llama3.1-8b_circular_trust_20260402.txt").read_text(
        encoding="utf-8"
    )
    report = analyze_graph(build_graph(parse_transcript(transcript), transcript_id="large-report"))
    out = render_report_ascii(report)

    assert "summary:" in out
    assert "phases:" in out
    assert "hotspots:" in out
    assert "[h1]" in out
    assert "cycle (severe)" in out
    assert "stats:" in out


def test_render_deepseek_cycle_trace_uses_heading_phases(samples_dir: Path) -> None:
    transcript = (samples_dir / "deepseek-r1-8b_circular_trust_20260402.txt").read_text(
        encoding="utf-8"
    )
    report = analyze_graph(build_graph(parse_transcript(transcript), transcript_id="deepseek-cycle"))
    out = render_report_ascii(report)

    assert "Defining Trust and the Role of Language Models" in out
    assert "Conclusion and Recommendations for Trust" in out
    assert "[p2]" in out


def test_render_handshake_trace_stays_full_mode(samples_dir: Path) -> None:
    transcript = (samples_dir / "deepseek-r1-8b_self_correction_handshake_20260402.txt").read_text(
        encoding="utf-8"
    )
    report = analyze_graph(build_graph(parse_transcript(transcript), transcript_id="handshake"))
    out = render_report_ascii(report)

    assert "[s1]" in out
    assert "phases:" not in out
    assert "hotspots:" not in out
