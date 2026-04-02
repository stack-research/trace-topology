from __future__ import annotations

from trace_topology.eval import evaluate_annotations


def test_eval_harness_runs(golden_dir, samples_dir) -> None:
    payload = evaluate_annotations(golden_dir, samples_dir)
    assert "summary" in payload
    assert payload["summary"]["count"] >= 1
    assert "avg_bond_precision" in payload["summary"]
