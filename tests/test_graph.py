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


def test_graph_adds_local_conclusion_support_from_multiple_prior_steps() -> None:
    transcript = (
        "The audit system must expose every action to all stakeholders.\n"
        "To guarantee privacy, the same actions must be hidden from all stakeholders.\n"
        "Therefore the log is fully visible and fully invisible at once."
    )
    steps = parse_transcript(transcript)
    graph = build_graph(steps, transcript_id="c")
    bonds = {(bond.source, bond.target, bond.type.value) for bond in graph.bonds}
    assert ("s1", "s3", "covalent") in bonds
    assert ("s2", "s3", "covalent") in bonds


def test_graph_branches_verification_from_last_conclusion() -> None:
    transcript = (
        "We split the people into glove and non-glove groups.\n"
        "Therefore the total number of handshakes is 13.\n"
        "This result is consistent with the alternative approach, so 28 - 15 = 13.\n"
        "The degree sum approach also confirms this."
    )
    steps = parse_transcript(transcript)
    graph = build_graph(steps, transcript_id="v")
    bonds = {(bond.source, bond.target, bond.type.value, bond.reason) for bond in graph.bonds}
    assert ("s2", "s3", "vanderwaals", "verification-branch") in bonds
    assert ("s2", "s4", "vanderwaals", "verification-branch") in bonds
