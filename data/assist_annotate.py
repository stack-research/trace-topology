"""
assist_annotate.py - bootstrap annotation drafts for human correction.

This mitigates the manual annotation bottleneck:
1) Generate draft steps/bonds/findings from current parser/graph/analyzer.
2) Human reviews and corrects the draft into golden annotations.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from trace_topology.analysis import analyze_graph
from trace_topology.graph import build_graph
from trace_topology.parser import parse_transcript

ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = ROOT / "samples"
ANNOTATIONS_DIR = ROOT / "samples" / "golden"


def draft_annotation(transcript_path: Path, annotator: str = "llm-assisted") -> dict:
    transcript = transcript_path.read_text(encoding="utf-8")
    steps = parse_transcript(transcript)
    graph = build_graph(steps, transcript_id=transcript_path.name)
    report = analyze_graph(graph)

    return {
        "transcript_file": transcript_path.name,
        "annotator": annotator,
        "annotation_date": date.today().isoformat(),
        "notes": (
            "AUTO-DRAFT. Review every step span, bond type, and finding before "
            "promoting to golden set."
        ),
        "steps": [
            {
                "id": step.id,
                "start_char": step.start_char,
                "end_char": step.end_char,
                "summary": step.summary,
                "step_type": step.step_type,
            }
            for step in steps
        ],
        "bonds": [
            {
                "from": bond.source,
                "to": bond.target,
                "type": bond.type.value,
                "confidence": round(bond.confidence, 2),
                "note": bond.reason,
            }
            for bond in graph.bonds
        ],
        "findings": [
            {
                "type": finding.type.value,
                "steps_involved": finding.steps_involved,
                "description": finding.description,
                "severity": finding.severity,
            }
            for finding in report.findings
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create assisted annotation drafts.")
    parser.add_argument("--transcript", default="*", help="Transcript filename or glob pattern.")
    parser.add_argument("--annotator", default="llm-assisted")
    parser.add_argument("--out-dir", default=str(ANNOTATIONS_DIR))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(SAMPLES_DIR.glob(args.transcript))
    txt_paths = [p for p in paths if p.suffix == ".txt"]
    if not txt_paths:
        print("No transcript files matched.")
        return

    for transcript_path in txt_paths:
        draft = draft_annotation(transcript_path, annotator=args.annotator)
        out_path = out_dir / f"{transcript_path.stem}.annotation.json"
        out_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        print(f"drafted {out_path.name}")


if __name__ == "__main__":
    main()
