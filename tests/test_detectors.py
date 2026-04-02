from __future__ import annotations

from trace_topology.analysis import (
    detect_bond_imbalance,
    detect_contradictions,
    detect_cycles,
    detect_dangling_nodes,
    detect_entropy_divergence,
    detect_unsupported_terminals,
)
from trace_topology.models import Bond, BondType, Step, TraceGraph


def test_detect_cycles_positive_and_negative() -> None:
    g_pos = TraceGraph(
        transcript_id="c1",
        steps=[Step("s1", "a", 0, 1), Step("s2", "b", 2, 3)],
        bonds=[
            Bond("s1", "s2", BondType.COVALENT),
            Bond("s2", "s1", BondType.COVALENT),
        ],
    )
    g_neg = TraceGraph(
        transcript_id="c2",
        steps=[Step("s1", "a", 0, 1), Step("s2", "b", 2, 3)],
        bonds=[Bond("s1", "s2", BondType.COVALENT)],
    )
    assert detect_cycles(g_pos)
    assert not detect_cycles(g_neg)


def test_detect_cycles_deduplicates_same_loop() -> None:
    graph = TraceGraph(
        transcript_id="c3",
        steps=[Step("s1", "a", 0, 1), Step("s2", "b", 2, 3), Step("s3", "c", 4, 5)],
        bonds=[
            Bond("s1", "s2", BondType.COVALENT),
            Bond("s2", "s3", BondType.COVALENT),
            Bond("s3", "s1", BondType.COVALENT),
            Bond("s1", "s3", BondType.COVALENT),
        ],
    )
    findings = detect_cycles(graph)
    assert len(findings) == 1


def test_detect_dangling_positive_and_negative() -> None:
    g_pos = TraceGraph(transcript_id="d1", steps=[Step("s1", "alone", 0, 5)], bonds=[])
    g_neg = TraceGraph(
        transcript_id="d2",
        steps=[Step("s1", "a", 0, 1), Step("s2", "b", 2, 3)],
        bonds=[Bond("s1", "s2", BondType.COVALENT)],
    )
    assert detect_dangling_nodes(g_pos)
    assert not detect_dangling_nodes(g_neg)


def test_detect_unsupported_terminal_positive_and_negative() -> None:
    g_pos = TraceGraph(
        transcript_id="u1",
        steps=[Step("s1", "therefore yes", 0, 12, step_type="conclusion")],
        bonds=[],
    )
    g_neg = TraceGraph(
        transcript_id="u2",
        steps=[
            Step("s1", "premise", 0, 7, step_type="claim"),
            Step("s2", "therefore yes", 8, 20, step_type="conclusion"),
        ],
        bonds=[Bond("s1", "s2", BondType.COVALENT)],
    )
    assert detect_unsupported_terminals(g_pos)
    assert not detect_unsupported_terminals(g_neg)


def test_detect_contradiction_positive_and_negative() -> None:
    g_pos = TraceGraph(
        transcript_id="k1",
        steps=[
            Step("s1", "the policy is safe", 0, 18),
            Step("s2", "the policy is not safe", 19, 42),
        ],
        bonds=[],
    )
    g_neg = TraceGraph(
        transcript_id="k2",
        steps=[
            Step("s1", "the policy is safe", 0, 18),
            Step("s2", "the policy is audited", 19, 40),
        ],
        bonds=[],
    )
    assert detect_contradictions(g_pos)
    assert not detect_contradictions(g_neg)


def test_detect_entropy_divergence_positive_and_negative() -> None:
    g_pos = TraceGraph(
        transcript_id="e1",
        steps=[
            Step("s1", "short", 0, 5),
            Step("s2", "small line", 6, 16),
            Step("s3", "medium line words", 17, 34),
            Step("s4", "very long diffuse sentence with many extra tokens and clauses", 35, 97),
        ],
        bonds=[],
    )
    g_neg = TraceGraph(
        transcript_id="e2",
        steps=[
            Step("s1", "medium words here", 0, 18),
            Step("s2", "medium words there", 19, 38),
            Step("s3", "medium words again", 39, 58),
            Step("s4", "medium words too", 59, 75),
        ],
        bonds=[],
    )
    assert detect_entropy_divergence(g_pos)
    assert not detect_entropy_divergence(g_neg)


def test_detect_bond_imbalance_positive_and_negative() -> None:
    g_pos = TraceGraph(
        transcript_id="b1",
        steps=[
            Step("s1", "a", 0, 1),
            Step("s2", "b", 2, 3),
            Step("s3", "c", 4, 5),
            Step("s4", "d", 6, 7),
        ],
        bonds=[
            Bond("s1", "s2", BondType.HYDROGEN),
            Bond("s2", "s3", BondType.HYDROGEN),
            Bond("s3", "s4", BondType.HYDROGEN),
            Bond("s1", "s3", BondType.VANDERWAALS),
        ],
    )
    g_neg = TraceGraph(
        transcript_id="b2",
        steps=[Step("s1", "a", 0, 1), Step("s2", "b", 2, 3), Step("s3", "c", 4, 5)],
        bonds=[
            Bond("s1", "s2", BondType.COVALENT),
            Bond("s2", "s3", BondType.HYDROGEN),
            Bond("s1", "s3", BondType.VANDERWAALS),
        ],
    )
    assert detect_bond_imbalance(g_pos)
    assert not detect_bond_imbalance(g_neg)
