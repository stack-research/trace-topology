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
def graph(transcript_path: str, out_path: str | None) -> None:
    transcript = _read_input(transcript_path)
    steps = parse_transcript(transcript)
    trace_graph = build_graph(steps, transcript_id=transcript_path)
    payload = trace_graph.to_dict()
    _write_json(out_path, payload)
    click.echo(render_graph_ascii(trace_graph))


@cli.command()
@click.argument("transcript_path")
@click.option("--out", "out_path", default=None, help="Write analysis artifact JSON.")
def analyze(transcript_path: str, out_path: str | None) -> None:
    transcript = _read_input(transcript_path)
    steps = parse_transcript(transcript)
    trace_graph = build_graph(steps, transcript_id=transcript_path)
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
