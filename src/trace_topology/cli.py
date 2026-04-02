from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from trace_topology.analysis import analyze_graph
from trace_topology.eval import evaluate_annotations
from trace_topology.graph import build_graph
from trace_topology.parser import parse_to_artifact, parse_transcript
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
def parse(transcript_path: str, out_path: str | None) -> None:
    transcript = _read_input(transcript_path)
    artifact = parse_to_artifact(transcript, transcript_id=transcript_path)
    _write_json(out_path, artifact)
    click.echo(json.dumps(artifact, indent=2))


@cli.command()
@click.argument("transcript_path")
@click.option("--out", "out_path", default=None, help="Write graph artifact JSON.")
@click.option(
    "--backend",
    "backend_name",
    type=click.Choice(["none", "ollama", "anthropic"]),
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
def graph(
    transcript_path: str,
    out_path: str | None,
    backend_name: str,
    model: str | None,
    base_url: str,
) -> None:
    transcript = _read_input(transcript_path)
    steps = parse_transcript(transcript)
    backend = _build_backend(backend_name, model=model, base_url=base_url)
    trace_graph = build_graph(steps, transcript_id=transcript_path, backend=backend)
    payload = trace_graph.to_dict()
    _write_json(out_path, payload)
    click.echo(render_graph_ascii(trace_graph))


@cli.command()
@click.argument("transcript_path")
@click.option("--out", "out_path", default=None, help="Write analysis artifact JSON.")
@click.option(
    "--backend",
    "backend_name",
    type=click.Choice(["none", "ollama", "anthropic"]),
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
def analyze(
    transcript_path: str,
    out_path: str | None,
    backend_name: str,
    model: str | None,
    base_url: str,
) -> None:
    transcript = _read_input(transcript_path)
    steps = parse_transcript(transcript)
    backend = _build_backend(backend_name, model=model, base_url=base_url)
    trace_graph = build_graph(steps, transcript_id=transcript_path, backend=backend)
    report = analyze_graph(trace_graph)
    payload = report.to_dict()
    _write_json(out_path, payload)
    click.echo(render_report_ascii(report))


@cli.command("eval")
@click.option("--annotations", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--samples", required=True, type=click.Path(path_type=Path, exists=True))
@click.option("--out", "out_path", default=None, help="Write eval report JSON.")
def eval_cmd(annotations: Path, samples: Path, out_path: str | None) -> None:
    payload = evaluate_annotations(annotations, samples)
    _write_json(out_path, payload)
    click.echo(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    cli()
