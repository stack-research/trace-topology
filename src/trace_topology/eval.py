from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from trace_topology.analysis import analyze_graph
from trace_topology.artifacts import eval_artifact
from trace_topology.graph import build_graph
from trace_topology.parser import parse_transcript


@dataclass(slots=True)
class EvalResult:
    transcript_file: str
    step_count_delta: int
    bond_precision: float
    bond_recall: float
    finding_precision: float
    finding_recall: float

    def to_dict(self) -> dict:
        return {
            "transcript_file": self.transcript_file,
            "step_count_delta": self.step_count_delta,
            "bond_precision": self.bond_precision,
            "bond_recall": self.bond_recall,
            "finding_precision": self.finding_precision,
            "finding_recall": self.finding_recall,
        }


def rank_eval_results(results: list[dict], limit: int = 5) -> list[dict]:
    ranked = sorted(
        results,
        key=lambda result: (
            -abs(int(result["step_count_delta"])),
            float(result["finding_recall"]),
            float(result["bond_recall"]),
            float(result["finding_precision"]),
            float(result["bond_precision"]),
            str(result["transcript_file"]),
        ),
    )
    worst_cases: list[dict] = []
    for result in ranked[:limit]:
        reasons: list[str] = []
        if result["step_count_delta"] != 0:
            reasons.append(f"step_count_delta={result['step_count_delta']}")
        if result["finding_recall"] < 1.0:
            reasons.append(f"finding_recall={result['finding_recall']:.2f}")
        if result["bond_recall"] < 1.0:
            reasons.append(f"bond_recall={result['bond_recall']:.2f}")
        if result["finding_precision"] < 1.0:
            reasons.append(f"finding_precision={result['finding_precision']:.2f}")
        if result["bond_precision"] < 1.0:
            reasons.append(f"bond_precision={result['bond_precision']:.2f}")
        if not reasons:
            reasons.append("matched_gold")
        worst_cases.append({**result, "reasons": reasons})
    return worst_cases


def _precision_recall(pred: set[tuple], gold: set[tuple]) -> tuple[float, float]:
    if not pred and not gold:
        return 1.0, 1.0
    tp = len(pred & gold)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 0.0
    return precision, recall


def evaluate_annotation(annotation_path: Path, samples_dir: Path) -> EvalResult:
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    transcript_file = annotation["transcript_file"]
    transcript_path = samples_dir / transcript_file
    transcript = transcript_path.read_text(encoding="utf-8")

    steps = parse_transcript(transcript)
    graph = build_graph(steps, transcript_id=transcript_file)
    report = analyze_graph(graph)

    gold_bonds = {(b["from"], b["to"], b["type"]) for b in annotation.get("bonds", [])}
    pred_bonds = {(b.source, b.target, b.type.value) for b in graph.bonds}
    bond_precision, bond_recall = _precision_recall(pred_bonds, gold_bonds)

    gold_findings = {
        (
            f["type"],
            tuple(sorted(f.get("steps_involved", []))),
        )
        for f in annotation.get("findings", [])
    }
    pred_findings = {
        (
            f.type.value,
            tuple(sorted(f.steps_involved)),
        )
        for f in report.findings
    }
    finding_precision, finding_recall = _precision_recall(pred_findings, gold_findings)

    return EvalResult(
        transcript_file=transcript_file,
        step_count_delta=len(steps) - len(annotation.get("steps", [])),
        bond_precision=bond_precision,
        bond_recall=bond_recall,
        finding_precision=finding_precision,
        finding_recall=finding_recall,
    )


def summary_meets_minimums(
    summary: dict,
    *,
    min_avg_bond_recall: float | None = None,
    min_avg_bond_precision: float | None = None,
    min_avg_finding_recall: float | None = None,
    min_avg_finding_precision: float | None = None,
) -> tuple[bool, list[str]]:
    """Return (ok, reasons) comparing eval summary averages to optional floors."""
    failures: list[str] = []
    if not summary or summary.get("count", 0) == 0:
        if any(
            x is not None
            for x in (
                min_avg_bond_recall,
                min_avg_bond_precision,
                min_avg_finding_recall,
                min_avg_finding_precision,
            )
        ):
            failures.append("no annotation results to score (empty summary)")
        return (not failures, failures)

    checks: list[tuple[str, str, float | None]] = [
        ("avg_bond_recall", "min_avg_bond_recall", min_avg_bond_recall),
        ("avg_bond_precision", "min_avg_bond_precision", min_avg_bond_precision),
        ("avg_finding_recall", "min_avg_finding_recall", min_avg_finding_recall),
        ("avg_finding_precision", "min_avg_finding_precision", min_avg_finding_precision),
    ]
    for key, label, floor in checks:
        if floor is None:
            continue
        value = float(summary.get(key, 0.0))
        if value < floor:
            failures.append(f"{key}={value:.4f} below {label}={floor}")
    return (not failures, failures)


def evaluate_annotations(annotation_dir: Path, samples_dir: Path) -> dict:
    results = []
    for path in sorted(annotation_dir.glob("*.json")):
        results.append(evaluate_annotation(path, samples_dir).to_dict())
    if not results:
        return eval_artifact([], {}, [])

    def avg(key: str) -> float:
        return sum(r[key] for r in results) / len(results)

    summary = {
        "count": len(results),
        "avg_step_count_delta": avg("step_count_delta"),
        "avg_bond_precision": avg("bond_precision"),
        "avg_bond_recall": avg("bond_recall"),
        "avg_finding_precision": avg("finding_precision"),
        "avg_finding_recall": avg("finding_recall"),
    }
    worst_cases = rank_eval_results(results)
    return eval_artifact(results, summary, worst_cases)
