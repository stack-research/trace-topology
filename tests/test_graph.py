from __future__ import annotations

from trace_topology.graph import build_graph
from trace_topology.parser import parse_transcript


def test_graph_builds_order_edges() -> None:
    transcript = "A because B. Wait, maybe C. Therefore D."
    steps = parse_transcript(transcript)
    graph = build_graph(steps, transcript_id="x")
    assert len(graph.steps) == len(steps)
    # Graph should not force adjacency edges; it should emit only evidenced bonds.
    assert len(graph.bonds) >= 1


def test_graph_metadata_has_bond_counts() -> None:
    steps = parse_transcript("Claim. Therefore conclusion.")
    graph = build_graph(steps, transcript_id="y")
    assert "bond_counts" in graph.metadata
