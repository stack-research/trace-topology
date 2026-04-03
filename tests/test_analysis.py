from __future__ import annotations

from trace_topology.analysis import analyze_graph, rank_findings
from trace_topology.graph import build_graph
from trace_topology.models import Finding, FindingType, Step, TraceGraph
from trace_topology.parser import parse_transcript


def test_analyze_returns_stats() -> None:
    steps = parse_transcript("A because B. Therefore C.")
    graph = build_graph(steps, transcript_id="t")
    report = analyze_graph(graph)
    assert "steps" in report.stats
    assert "findings" in report.stats
    assert "by_severity" in report.stats
    assert "top_finding_type" in report.stats


def test_detects_unsupported_terminal() -> None:
    steps = parse_transcript("Therefore the answer is 42.")
    graph = build_graph(steps, transcript_id="u")
    report = analyze_graph(graph)
    types = {f.type.value for f in report.findings}
    assert "unsupported_terminal" in types


def test_targeted_synthetic_primary_findings(samples_dir) -> None:
    expected = {
        "synthetic_cycle_trust_0001.txt": "cycle",
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


def test_closed_loop_cycle_is_canonicalized(samples_dir) -> None:
    transcript = (samples_dir / "deepseek-r1-8b_circular_closed_loop_20260402.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)
    report = analyze_graph(build_graph(steps, transcript_id="closed-loop"))

    cycles = [finding.steps_involved for finding in report.findings if finding.type.value == "cycle"]
    assert cycles == [["s1", "s2", "s3", "s4"]]
    assert "entropy_divergence" not in {finding.type.value for finding in report.findings}


def test_rank_findings_orders_by_severity_score_type_then_step() -> None:
    graph = TraceGraph(
        transcript_id="rank",
        steps=[
            Step("s1", "A.", 0, 2),
            Step("s2", "B.", 3, 5),
            Step("s3", "C.", 6, 8),
            Step("s4", "D.", 9, 11),
        ],
        bonds=[],
    )
    findings = [
        Finding(FindingType.DANGLING, ["s4"], "dangling", severity="low", score=0.9),
        Finding(FindingType.CYCLE, ["s3"], "cycle", severity="severe", score=0.8),
        Finding(FindingType.CONTRADICTION, ["s2"], "contradiction", severity="severe", score=0.8),
        Finding(FindingType.BOND_IMBALANCE, ["s1"], "imbalance", severity="moderate", score=0.95),
    ]

    ranked = rank_findings(findings, graph)

    assert [finding.type.value for finding in ranked] == [
        "contradiction",
        "cycle",
        "bond_imbalance",
        "dangling",
    ]


def test_contradiction_sorts_ahead_of_weaker_secondary_findings(samples_dir) -> None:
    transcript = (samples_dir / "synthetic_contradiction_privacy_0001.txt").read_text(encoding="utf-8")
    report = analyze_graph(build_graph(parse_transcript(transcript), transcript_id="contradiction"))

    assert report.findings
    assert report.findings[0].type.value == "contradiction"
