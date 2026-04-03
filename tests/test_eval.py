from __future__ import annotations

from pathlib import Path

from trace_topology.eval import (
    evaluate_annotation,
    evaluate_annotations,
    summary_meets_minimums,
)


def test_eval_harness_runs(golden_dir, samples_dir) -> None:
    payload = evaluate_annotations(golden_dir, samples_dir)
    assert "summary" in payload
    assert payload["summary"]["count"] >= 1
    assert "avg_bond_precision" in payload["summary"]


def test_summary_meets_minimums_empty_with_threshold_fails() -> None:
    ok, reasons = summary_meets_minimums({}, min_avg_bond_recall=0.5)
    assert ok is False
    assert reasons


def test_summary_meets_minimums_passes_when_no_thresholds() -> None:
    ok, _ = summary_meets_minimums({"count": 2, "avg_bond_recall": 0.0})
    assert ok is True


def test_eval_targeted_synthetic_finding_recall(golden_dir, samples_dir) -> None:
    targeted = [
        "synthetic_cycle_trust_0001.annotation.json",
        "synthetic_contradiction_privacy_0001.annotation.json",
        "synthetic_dangling_multipart_0001.annotation.json",
        "synthetic_entropy_openended_0001.annotation.json",
        "synthetic_unsupported_terminal_0001.annotation.json",
    ]
    for name in targeted:
        result = evaluate_annotation(Path(golden_dir / name), samples_dir)
        assert result.finding_recall > 0.0, name


def test_eval_handshake_regressions(golden_dir, samples_dir) -> None:
    deepseek = evaluate_annotation(
        Path(golden_dir / "deepseek-r1-8b_self_correction_handshake_20260402.annotation.json"),
        samples_dir,
    )
    llama = evaluate_annotation(
        Path(golden_dir / "llama3.1-8b_self_correction_handshake_20260402.annotation.json"),
        samples_dir,
    )

    assert deepseek.step_count_delta == 0
    assert deepseek.finding_precision == 1.0
    assert deepseek.finding_recall == 1.0
    assert llama.step_count_delta == 0
    assert llama.finding_precision == 1.0
    assert llama.finding_recall == 1.0


def test_eval_cycle_regressions(golden_dir, samples_dir) -> None:
    synthetic = evaluate_annotation(
        Path(golden_dir / "synthetic_cycle_trust_0001.annotation.json"),
        samples_dir,
    )
    closed_loop = evaluate_annotation(
        Path(golden_dir / "deepseek-r1-8b_circular_closed_loop_20260402.annotation.json"),
        samples_dir,
    )
    deepseek_trust = evaluate_annotation(
        Path(golden_dir / "deepseek-r1-8b_circular_trust_20260402.annotation.json"),
        samples_dir,
    )
    llama_trust = evaluate_annotation(
        Path(golden_dir / "llama3.1-8b_circular_trust_20260402.annotation.json"),
        samples_dir,
    )

    assert synthetic.finding_recall > 0.0
    assert closed_loop.finding_recall > 0.0
    assert deepseek_trust.step_count_delta == 0
    assert deepseek_trust.finding_recall > 0.0
    assert llama_trust.step_count_delta == 0
    assert llama_trust.finding_recall > 0.0


def test_eval_summary_meets_accuracy_floors(golden_dir, samples_dir) -> None:
    payload = evaluate_annotations(golden_dir, samples_dir)
    summary = payload["summary"]

    assert summary["avg_bond_precision"] >= 0.80
    assert summary["avg_bond_recall"] >= 0.88
    assert summary["avg_finding_precision"] >= 0.80
    assert summary["avg_finding_recall"] >= 0.75
