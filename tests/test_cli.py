from __future__ import annotations

from click.testing import CliRunner

from trace_topology.cli import cli


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
