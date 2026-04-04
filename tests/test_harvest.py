from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_harvest_module(repo_root: Path):
    harvest_path = repo_root / "data" / "harvest.py"
    spec = importlib.util.spec_from_file_location("trace_topology_harvest", harvest_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_uqm_transcripts_defaults_to_curated_crack_subset(repo_root: Path, tmp_path: Path) -> None:
    harvest = _load_harvest_module(repo_root)
    fixture = repo_root / "tests" / "fixtures" / "uqm" / "run_fixture.json"
    uqm_dir = tmp_path / "uqm"
    uqm_dir.mkdir()
    (uqm_dir / fixture.name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    transcripts = harvest.load_uqm_transcripts(uqm_data_dir=uqm_dir)

    assert [transcript.id for transcript in transcripts] == [
        "fa2ef95f",
        "9d76614c",
        "28913ff7",
    ]
    assert [transcript.filename_base() for transcript in transcripts] == [
        "llama3.1-8b_uqm_absence_mapping_fa2ef95f",
        "llama3.1-8b_uqm_depth_test_9d76614c",
        "llama3.1-8b_uqm_strange_loop_28913ff7",
    ]


def test_load_uqm_transcripts_all_filter_includes_noncurated_results(repo_root: Path, tmp_path: Path) -> None:
    harvest = _load_harvest_module(repo_root)
    fixture = repo_root / "tests" / "fixtures" / "uqm" / "run_fixture.json"
    uqm_dir = tmp_path / "uqm"
    uqm_dir.mkdir()
    (uqm_dir / fixture.name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    transcripts = harvest.load_uqm_transcripts(filter_type="all", uqm_data_dir=uqm_dir)

    assert [transcript.id for transcript in transcripts] == [
        "fa2ef95f",
        "9d76614c",
        "engage000",
        "28913ff7",
    ]


def test_load_uqm_transcripts_missing_dir_returns_empty(repo_root: Path, tmp_path: Path, capsys) -> None:
    harvest = _load_harvest_module(repo_root)

    transcripts = harvest.load_uqm_transcripts(uqm_data_dir=tmp_path / "missing")

    captured = capsys.readouterr()
    assert transcripts == []
    assert "WARNING: UQM data dir not found" in captured.err


def test_load_uqm_transcripts_preserves_provenance_metadata(repo_root: Path, tmp_path: Path) -> None:
    harvest = _load_harvest_module(repo_root)
    fixture = repo_root / "tests" / "fixtures" / "uqm" / "run_fixture.json"
    uqm_dir = tmp_path / "uqm"
    uqm_dir.mkdir()
    (uqm_dir / fixture.name).write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    transcript = harvest.load_uqm_transcripts(uqm_data_dir=uqm_dir)[0]

    assert transcript.metadata["uqm_import_contract_version"] == 1
    assert transcript.metadata["uqm_run_file"] == "run_fixture.json"
    assert transcript.metadata["uqm_probe_id"] == "fa2ef95f"
    assert transcript.metadata["uqm_probe_name"] == "absence_mapping"
    assert transcript.metadata["heuristic_classification"] == "crack"
    assert transcript.metadata["judge_classification"] == "engage"
    assert transcript.metadata["response_backend"] == "ollama"
    assert transcript.metadata["response_metadata"] == {"total_duration_ns": 3941510167}
