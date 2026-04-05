from __future__ import annotations

from pathlib import Path

from trace_topology.analysis import analyze_graph
from trace_topology.artifacts import SCHEMA_VERSION, eval_artifact, graph_artifact
from trace_topology.eval import evaluate_annotations
from trace_topology.graph import build_graph
from trace_topology.models import AnalysisReport, Finding, FindingType, Step, TraceGraph
from trace_topology.parser import parse_to_artifact, parse_transcript


def test_parse_artifact_has_schema_header() -> None:
    artifact = parse_to_artifact("Claim.\nTherefore conclusion.", transcript_id="sample.txt")

    assert artifact["artifact_type"] == "parse"
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["config"] == {"parser_granularity": "heuristic"}
    assert artifact["transcript_id"] == "sample.txt"
    assert "steps" in artifact
    assert "stats" in artifact


def test_graph_artifact_has_schema_header() -> None:
    graph = build_graph(parse_transcript("Claim.\nTherefore conclusion."), transcript_id="graph.txt")
    artifact = graph_artifact(graph)

    assert artifact["artifact_type"] == "graph"
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["config"] == {"parser_granularity": "heuristic"}
    assert artifact["transcript_id"] == "graph.txt"
    assert "steps" in artifact
    assert "bonds" in artifact
    assert "metadata" in artifact


def test_analysis_artifact_has_schema_header_and_nested_graph_shape() -> None:
    graph = build_graph(
        parse_transcript("Trustworthy models should be trusted.\nTherefore they are reliable."),
        transcript_id="analysis.txt",
    )
    report = analyze_graph(graph)
    artifact = report.to_dict()

    assert artifact["artifact_type"] == "analysis"
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["config"] == {"parser_granularity": "heuristic"}
    assert set(artifact["graph"]) == {"transcript_id", "steps", "bonds", "metadata"}
    assert "findings" in artifact
    assert "stats" in artifact


def test_eval_artifact_has_schema_header(samples_dir: Path, golden_dir: Path) -> None:
    payload = evaluate_annotations(golden_dir, samples_dir)

    assert payload["artifact_type"] == "eval"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["config"] == {"parser_granularity": "heuristic"}
    assert "results" in payload
    assert "summary" in payload
    assert "worst_cases" in payload
    assert "cohorts" in payload


def test_eval_artifact_helper_preserves_existing_payload_shape() -> None:
    payload = eval_artifact(results=[{"transcript_file": "x.txt"}], summary={"count": 1})

    assert payload == {
        "artifact_type": "eval",
        "schema_version": SCHEMA_VERSION,
        "config": {"parser_granularity": "heuristic"},
        "results": [{"transcript_file": "x.txt"}],
        "summary": {"count": 1},
        "worst_cases": [],
        "cohorts": {},
    }


def test_analysis_artifact_sorts_findings_highest_priority_first() -> None:
    report = AnalysisReport(
        graph=TraceGraph(
            transcript_id="artifact-rank",
            steps=[Step("s1", "A.", 0, 2), Step("s2", "B.", 3, 5)],
            bonds=[],
        ),
        findings=[
            Finding(FindingType.DANGLING, ["s2"], "dangling", severity="low", score=0.4),
            Finding(FindingType.UNSUPPORTED_TERMINAL, ["s1"], "unsupported", severity="severe", score=0.85),
        ],
        stats={},
    )

    payload = report.to_dict()

    assert payload["config"] == {"parser_granularity": "heuristic"}
    assert [finding["type"] for finding in payload["findings"]] == [
        "unsupported_terminal",
        "dangling",
    ]
