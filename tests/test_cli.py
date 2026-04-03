from __future__ import annotations

import json
import sys

from click.testing import CliRunner

from trace_topology.cli import _build_backend, cli


def test_analyze_accepts_backend_flag(tmp_path) -> None:
    transcript_path = tmp_path / "trace.txt"
    transcript_path.write_text("Therefore the answer is 42.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(transcript_path), "--backend", "none"])

    assert result.exit_code == 0
    assert "unsupported_terminal" in result.output


def test_graph_accepts_backend_flag(tmp_path) -> None:
    transcript_path = tmp_path / "trace.txt"
    transcript_path.write_text("A because B.\nTherefore C.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["graph", str(transcript_path), "--backend", "none"])

    assert result.exit_code == 0
    assert "legend:" in result.output


def test_analyze_fail_on_findings_exits_nonzero(tmp_path) -> None:
    transcript_path = tmp_path / "trace.txt"
    transcript_path.write_text("Therefore the answer is 42.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli, ["analyze", str(transcript_path), "--backend", "none", "--fail-on-findings"]
    )

    assert result.exit_code == 1


def test_eval_min_threshold_exits_nonzero(golden_dir, samples_dir) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "eval",
            "--annotations",
            str(golden_dir),
            "--samples",
            str(samples_dir),
            "--min-avg-bond-recall",
            "1.01",
        ],
    )

    assert result.exit_code == 1
    assert "below" in result.output or "annotation" in result.output.lower()


def test_parse_out_file_has_schema_header(tmp_path) -> None:
    transcript_path = tmp_path / "trace.txt"
    out_path = tmp_path / "steps.json"
    transcript_path.write_text("Claim.\nTherefore conclusion.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["parse", str(transcript_path), "--out", str(out_path)])

    assert result.exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "parse"
    assert payload["schema_version"] == 1


def test_graph_out_file_has_schema_header(tmp_path) -> None:
    transcript_path = tmp_path / "trace.txt"
    out_path = tmp_path / "graph.json"
    transcript_path.write_text("Claim.\nTherefore conclusion.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["graph", str(transcript_path), "--backend", "none", "--out", str(out_path)])

    assert result.exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "graph"
    assert payload["schema_version"] == 1


def test_analyze_out_file_has_schema_header(tmp_path) -> None:
    transcript_path = tmp_path / "trace.txt"
    out_path = tmp_path / "analysis.json"
    transcript_path.write_text("Claim.\nTherefore conclusion.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["analyze", str(transcript_path), "--backend", "none", "--out", str(out_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "analysis"
    assert payload["schema_version"] == 1


def test_eval_out_file_has_schema_header(tmp_path, golden_dir, samples_dir) -> None:
    out_path = tmp_path / "eval.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "eval",
            "--annotations",
            str(golden_dir),
            "--samples",
            str(samples_dir),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "eval"
    assert payload["schema_version"] == 1


def test_backend_none_does_not_import_backends_module(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "trace_topology.backends", raising=False)

    backend = _build_backend("none")

    assert backend is None
    assert "trace_topology.backends" not in sys.modules


def test_graph_ollama_missing_dependency_has_install_hint(tmp_path, monkeypatch) -> None:
    transcript_path = tmp_path / "trace.txt"
    transcript_path.write_text("Claim.\nTherefore conclusion.", encoding="utf-8")

    import trace_topology.backends as backends

    def fail_import():
        raise RuntimeError("Install optional dependency: pip install trace-topology[ollama]")

    monkeypatch.setattr(backends, "_import_requests", fail_import)
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", str(transcript_path), "--backend", "ollama"])

    assert result.exit_code == 1
    assert "trace-topology[ollama]" in result.output


def test_analyze_anthropic_missing_api_key_has_clear_error(tmp_path, monkeypatch) -> None:
    transcript_path = tmp_path / "trace.txt"
    transcript_path.write_text("Claim.\nTherefore conclusion.", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", str(transcript_path), "--backend", "anthropic"])

    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY" in result.output
