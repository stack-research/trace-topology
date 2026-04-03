from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from trace_topology.cli import cli


def test_readme_sample_file_flow(samples_dir: Path, golden_dir: Path, tmp_path: Path) -> None:
    sample = samples_dir / "deepseek-r1-8b_self_correction_handshake_20260402.txt"
    parse_out = tmp_path / "steps.handshake.json"
    graph_out = tmp_path / "graph.handshake.json"
    analysis_out = tmp_path / "analysis.handshake.json"
    eval_out = tmp_path / "eval.json"

    runner = CliRunner()

    parse_result = runner.invoke(cli, ["parse", str(sample), "--out", str(parse_out)])
    graph_result = runner.invoke(
        cli,
        ["graph", str(sample), "--backend", "none", "--out", str(graph_out)],
    )
    analysis_result = runner.invoke(
        cli,
        ["analyze", str(sample), "--backend", "none", "--out", str(analysis_out)],
    )
    eval_result = runner.invoke(
        cli,
        [
            "eval",
            "--annotations",
            str(golden_dir),
            "--samples",
            str(samples_dir),
            "--out",
            str(eval_out),
        ],
    )

    assert parse_result.exit_code == 0
    assert graph_result.exit_code == 0
    assert analysis_result.exit_code == 0
    assert eval_result.exit_code == 0
    assert json.loads(parse_out.read_text(encoding="utf-8"))["artifact_type"] == "parse"
    assert json.loads(graph_out.read_text(encoding="utf-8"))["artifact_type"] == "graph"
    assert json.loads(analysis_out.read_text(encoding="utf-8"))["artifact_type"] == "analysis"
    assert json.loads(eval_out.read_text(encoding="utf-8"))["artifact_type"] == "eval"
