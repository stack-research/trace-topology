from __future__ import annotations

from pathlib import Path

from trace_topology.analysis import analyze_graph
from trace_topology.artifacts import SCHEMA_VERSION, eval_artifact, graph_artifact
from trace_topology.eval import evaluate_annotations
from trace_topology.graph import build_graph
from trace_topology.parser import parse_to_artifact, parse_transcript


def test_parse_artifact_has_schema_header() -> None:
    artifact = parse_to_artifact("Claim.\nTherefore conclusion.", transcript_id="sample.txt")

    assert artifact["artifact_type"] == "parse"
    assert artifact["schema_version"] == SCHEMA_VERSION
    assert artifact["transcript_id"] == "sample.txt"
    assert "steps" in artifact
    assert "stats" in artifact


def test_graph_artifact_has_schema_header() -> None:
    graph = build_graph(parse_transcript("Claim.\nTherefore conclusion."), transcript_id="graph.txt")
    artifact = graph_artifact(graph)

    assert artifact["artifact_type"] == "graph"
    assert artifact["schema_version"] == SCHEMA_VERSION
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
    assert set(artifact["graph"]) == {"transcript_id", "steps", "bonds", "metadata"}
    assert "findings" in artifact
    assert "stats" in artifact


def test_eval_artifact_has_schema_header(samples_dir: Path, golden_dir: Path) -> None:
    payload = evaluate_annotations(golden_dir, samples_dir)

    assert payload["artifact_type"] == "eval"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "results" in payload
    assert "summary" in payload


def test_eval_artifact_helper_preserves_existing_payload_shape() -> None:
    payload = eval_artifact(results=[{"transcript_file": "x.txt"}], summary={"count": 1})

    assert payload == {
        "artifact_type": "eval",
        "schema_version": SCHEMA_VERSION,
        "results": [{"transcript_file": "x.txt"}],
        "summary": {"count": 1},
    }
