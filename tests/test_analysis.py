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


def test_targeted_synthetic_primary_findings(samples_dir) -> None:
    expected = {
        "synthetic_contradiction_privacy_0001.txt": "contradiction",
        "synthetic_dangling_multipart_0001.txt": "dangling",
        "synthetic_entropy_openended_0001.txt": "entropy_divergence",
        "synthetic_unsupported_terminal_0001.txt": "unsupported_terminal",
    }
    for name, finding_type in expected.items():
        transcript = (samples_dir / name).read_text(encoding="utf-8")
        steps = parse_transcript(transcript)
        graph = build_graph(steps, transcript_id=name)
        report = analyze_graph(graph)
        types = {finding.type.value for finding in report.findings}
        assert finding_type in types, name


def test_deepseek_handshake_is_clean(samples_dir) -> None:
    transcript = (samples_dir / "deepseek-r1-8b_self_correction_handshake_20260402.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)
    report = analyze_graph(build_graph(steps, transcript_id="deepseek-handshake"))

    assert report.findings == []


def test_llama_handshake_collapses_to_single_unsupported_terminal(samples_dir) -> None:
    transcript = (samples_dir / "llama3.1-8b_self_correction_handshake_20260402.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)
    report = analyze_graph(build_graph(steps, transcript_id="llama-handshake"))

    finding_types = [finding.type.value for finding in report.findings]
    assert finding_types == ["unsupported_terminal"]
