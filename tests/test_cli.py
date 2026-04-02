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
