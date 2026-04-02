from __future__ import annotations

import json
from pathlib import Path


def test_samples_have_trace_and_metadata(samples_dir: Path) -> None:
    txt = sorted(samples_dir.glob("*.txt"))
    meta = sorted(samples_dir.glob("*.json"))
    assert txt, "Expected seeded transcript files in data/samples/"
    assert meta, "Expected paired metadata JSON files in data/samples/"


def test_golden_annotations_reference_existing_transcripts(
    samples_dir: Path, golden_dir: Path
) -> None:
    annotations = sorted(golden_dir.glob("*.json"))
    assert annotations, "Expected golden annotation files."
    for ann_path in annotations:
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        transcript = samples_dir / ann["transcript_file"]
        assert transcript.exists(), f"Missing transcript for {ann_path.name}"


def test_annotation_step_ranges_and_bonds(samples_dir: Path, golden_dir: Path) -> None:
    for ann_path in sorted(golden_dir.glob("*.json")):
        ann = json.loads(ann_path.read_text(encoding="utf-8"))
        transcript_text = (samples_dir / ann["transcript_file"]).read_text(encoding="utf-8")
        step_ids = {s["id"] for s in ann["steps"]}
        for step in ann["steps"]:
            assert 0 <= step["start_char"] < step["end_char"] <= len(transcript_text)
        for bond in ann["bonds"]:
            assert bond["from"] in step_ids
            assert bond["to"] in step_ids
