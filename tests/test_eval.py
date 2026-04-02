from __future__ import annotations

from pathlib import Path

from trace_topology.eval import evaluate_annotation
from trace_topology.eval import evaluate_annotations


def test_eval_harness_runs(golden_dir, samples_dir) -> None:
    payload = evaluate_annotations(golden_dir, samples_dir)
    assert "summary" in payload
    assert payload["summary"]["count"] >= 1
    assert "avg_bond_precision" in payload["summary"]


def test_eval_targeted_synthetic_finding_recall(golden_dir, samples_dir) -> None:
    targeted = [
        "synthetic_contradiction_privacy_0001.annotation.json",
        "synthetic_dangling_multipart_0001.annotation.json",
        "synthetic_entropy_openended_0001.annotation.json",
        "synthetic_unsupported_terminal_0001.annotation.json",
    ]
    for name in targeted:
        result = evaluate_annotation(Path(golden_dir / name), samples_dir)
        assert result.finding_recall > 0.0, name
