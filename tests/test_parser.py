from __future__ import annotations

from trace_topology.parser import parse_transcript


def test_parse_numbered_and_freeform_steps() -> None:
    transcript = (
        "1) First claim\n"
        "2) Because second claim.\n"
        "Wait, correction.\n"
        "Therefore conclusion."
    )
    steps = parse_transcript(transcript)
    assert len(steps) >= 3
    assert steps[0].id == "s1"
    assert all(step.start_char < step.end_char for step in steps)


def test_parse_thinking_block_like_markup() -> None:
    transcript = "<thinking>\nmaybe x\nwait no\n</thinking>\ntherefore y"
    steps = parse_transcript(transcript)
    assert len(steps) >= 2
