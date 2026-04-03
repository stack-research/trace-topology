from __future__ import annotations

from dataclasses import asdict

from trace_topology.models import AnalysisReport, Bond, Step, TraceGraph

SCHEMA_VERSION = 1


def _base_header(artifact_type: str) -> dict:
    return {
        "artifact_type": artifact_type,
        "schema_version": SCHEMA_VERSION,
    }


def step_payload(step: Step) -> dict:
    return asdict(step)


def bond_payload(bond: Bond) -> dict:
    return {
        "source": bond.source,
        "target": bond.target,
        "type": bond.type.value,
        "confidence": bond.confidence,
        "reason": bond.reason,
    }


def graph_payload(graph: TraceGraph) -> dict:
    return {
        "transcript_id": graph.transcript_id,
        "steps": [step_payload(step) for step in graph.steps],
        "bonds": [bond_payload(bond) for bond in graph.bonds],
        "metadata": graph.metadata,
    }


def parse_artifact(transcript_id: str, steps: list[Step], char_count: int) -> dict:
    return {
        **_base_header("parse"),
        "transcript_id": transcript_id,
        "steps": [step_payload(step) for step in steps],
        "stats": {"step_count": len(steps), "char_count": char_count},
    }


def graph_artifact(graph: TraceGraph) -> dict:
    return {
        **_base_header("graph"),
        **graph_payload(graph),
    }


def analysis_artifact(report: AnalysisReport) -> dict:
    from trace_topology.analysis import rank_findings

    ranked_findings = rank_findings(report.findings, report.graph)
    return {
        **_base_header("analysis"),
        "graph": graph_payload(report.graph),
        "findings": [finding.to_dict() for finding in ranked_findings],
        "stats": report.stats,
    }


def eval_artifact(results: list[dict], summary: dict) -> dict:
    return {
        **_base_header("eval"),
        "results": results,
        "summary": summary,
    }
