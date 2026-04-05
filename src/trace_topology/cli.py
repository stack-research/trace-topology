from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from trace_topology.analysis import analyze_graph, finding_matches_gate
from trace_topology.artifacts import graph_artifact
from trace_topology.eval import evaluate_annotations, summary_meets_minimums
from trace_topology.graph import build_graph
from trace_topology.parser import PARSER_GRANULARITIES, parse_to_artifact, parse_transcript
from trace_topology.render import render_graph_ascii, render_report_ascii


def _build_backend(
    backend_name: str,
    model: str | None = None,
    base_url: str = "http://localhost:11434",
):
    if backend_name == "none":
        return None

    if backend_name == "ollama":
        from trace_topology.backends import OllamaBackend

        return OllamaBackend(model=model or "llama3.1:8b", base_url=base_url)

    if backend_name == "anthropic":
        from trace_topology.backends import AnthropicBackend

        return AnthropicBackend(model=model or "claude-3-5-sonnet-latest")

    if backend_name == "openai":
        from trace_topology.backends import OpenAIBackend

        return OpenAIBackend(model=model or "gpt-5-mini")

    raise click.BadParameter(f"Unsupported backend: {backend_name}")


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _write_json(path: str | None, payload: dict) -> None:
    if path:
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


@click.group()
def cli() -> None:
    """trace-topology CLI."""


@cli.command()
@click.argument("transcript_path")
@click.option("--out", "out_path", default=None, help="Write parse artifact JSON.")
@click.option(
    "--granularity",
    type=click.Choice(PARSER_GRANULARITIES),
    default="heuristic",
    show_default=True,
    help="Parser step-segmentation mode.",
)
def parse(transcript_path: str, out_path: str | None, granularity: str) -> None:
    transcript = _read_input(transcript_path)
    artifact = parse_to_artifact(
        transcript,
        transcript_id=transcript_path,
        granularity=granularity,
    )
    _write_json(out_path, artifact)
    click.echo(json.dumps(artifact, indent=2))


@cli.command()
@click.argument("transcript_path")
@click.option("--out", "out_path", default=None, help="Write graph artifact JSON.")
@click.option(
    "--backend",
    "backend_name",
    type=click.Choice(["none", "ollama", "anthropic", "openai"]),
    default="none",
    show_default=True,
    help="Optional bond-classification backend.",
)
@click.option("--model", default=None, help="Backend model name.")
@click.option(
    "--base-url",
    default="http://localhost:11434",
    show_default=True,
    help="Base URL for the Ollama backend.",
)
@click.option(
    "--granularity",
    type=click.Choice(PARSER_GRANULARITIES),
    default="heuristic",
    show_default=True,
    help="Parser step-segmentation mode.",
)
def graph(
    transcript_path: str,
    out_path: str | None,
    backend_name: str,
    model: str | None,
    base_url: str,
    granularity: str,
) -> None:
    transcript = _read_input(transcript_path)
    steps = parse_transcript(transcript, granularity=granularity)
    try:
        backend = _build_backend(backend_name, model=model, base_url=base_url)
        trace_graph = build_graph(
            steps,
            transcript_id=transcript_path,
            backend=backend,
            parser_granularity=granularity,
        )
        payload = graph_artifact(trace_graph)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    _write_json(out_path, payload)
    click.echo(render_graph_ascii(trace_graph))


@cli.command()
@click.argument("transcript_path")
@click.option("--out", "out_path", default=None, help="Write analysis artifact JSON.")
@click.option(
    "--backend",
    "backend_name",
    type=click.Choice(["none", "ollama", "anthropic", "openai"]),
    default="none",
    show_default=True,
    help="Optional bond-classification backend.",
)
@click.option("--model", default=None, help="Backend model name.")
@click.option(
    "--base-url",
    default="http://localhost:11434",
    show_default=True,
    help="Base URL for the Ollama backend.",
)
@click.option(
    "--fail-on-findings",
    is_flag=True,
    default=False,
    help="Exit with code 1 if the analysis report contains any findings (for CI gates).",
)
@click.option(
    "--fail-on-min-severity",
    type=click.Choice(["low", "moderate", "severe"]),
    default=None,
    help="Exit with code 1 if any finding is at or above this severity.",
)
@click.option(
    "--fail-on-min-score",
    type=float,
    default=None,
    metavar="F",
    help="Exit with code 1 if any finding has score >= F.",
)
@click.option(
    "--granularity",
    type=click.Choice(PARSER_GRANULARITIES),
    default="heuristic",
    show_default=True,
    help="Parser step-segmentation mode.",
)
def analyze(
    transcript_path: str,
    out_path: str | None,
    backend_name: str,
    model: str | None,
    base_url: str,
    fail_on_findings: bool,
    fail_on_min_severity: str | None,
    fail_on_min_score: float | None,
    granularity: str,
) -> None:
    transcript = _read_input(transcript_path)
    steps = parse_transcript(transcript, granularity=granularity)
    try:
        backend = _build_backend(backend_name, model=model, base_url=base_url)
        trace_graph = build_graph(
            steps,
            transcript_id=transcript_path,
            backend=backend,
            parser_granularity=granularity,
        )
        report = analyze_graph(trace_graph)
        payload = report.to_dict()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    _write_json(out_path, payload)
    click.echo(render_report_ascii(report))
    if fail_on_findings and report.findings:
        raise click.exceptions.Exit(1)
    if (fail_on_min_severity is not None or fail_on_min_score is not None) and any(
        finding_matches_gate(
            finding,
            min_severity=fail_on_min_severity,
            min_score=fail_on_min_score,
        )
        for finding in report.findings
    ):
        raise click.exceptions.Exit(1)


@cli.command("eval")
@click.option("--annotations", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--samples", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--out", "out_path", default=None, help="Write eval report JSON.")
@click.option(
    "--min-avg-bond-recall",
    type=float,
    default=None,
    metavar="F",
    help="If set, exit 1 when summary avg_bond_recall is below F.",
)
@click.option(
    "--min-avg-bond-precision",
    type=float,
    default=None,
    metavar="F",
    help="If set, exit 1 when summary avg_bond_precision is below F.",
)
@click.option(
    "--min-avg-finding-recall",
    type=float,
    default=None,
    metavar="F",
    help="If set, exit 1 when summary avg_finding_recall is below F.",
)
@click.option(
    "--min-avg-finding-precision",
    type=float,
    default=None,
    metavar="F",
    help="If set, exit 1 when summary avg_finding_precision is below F.",
)
@click.option(
    "--granularity",
    type=click.Choice(PARSER_GRANULARITIES),
    default="heuristic",
    show_default=True,
    help="Parser step-segmentation mode.",
)
def eval_cmd(
    annotations: Path,
    samples: Path,
    out_path: str | None,
    min_avg_bond_recall: float | None,
    min_avg_bond_precision: float | None,
    min_avg_finding_recall: float | None,
    min_avg_finding_precision: float | None,
    granularity: str,
) -> None:
    payload = evaluate_annotations(annotations, samples, granularity=granularity)
    _write_json(out_path, payload)
    click.echo(json.dumps(payload["summary"], indent=2))
    if payload["worst_cases"]:
        click.echo("worst-cases:")
        for case in payload["worst_cases"]:
            reasons = ", ".join(case["reasons"])
            click.echo(
                "  - "
                f"{case['transcript_file']}: "
                f"step_delta={case['step_count_delta']} "
                f"bond_recall={case['bond_recall']:.2f} "
                f"finding_recall={case['finding_recall']:.2f} "
                f"({reasons})"
            )
    if payload["cohorts"]:
        click.echo("cohorts:")
        for name, summary in payload["cohorts"].items():
            click.echo(
                "  - "
                f"{name}: "
                f"count={summary['count']} "
                f"step_delta={summary['avg_step_count_delta']:.2f} "
                f"bond_recall={summary['avg_bond_recall']:.2f} "
                f"finding_recall={summary['avg_finding_recall']:.2f}"
            )
    ok, reasons = summary_meets_minimums(
        payload["summary"],
        min_avg_bond_recall=min_avg_bond_recall,
        min_avg_bond_precision=min_avg_bond_precision,
        min_avg_finding_recall=min_avg_finding_recall,
        min_avg_finding_precision=min_avg_finding_precision,
    )
    if not ok:
        for line in reasons:
            click.echo(line, err=True)
        raise click.exceptions.Exit(1)


if __name__ == "__main__":
    cli()
