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


def test_parse_targeted_synthetic_step_counts(samples_dir) -> None:
    expected_counts = {
        "synthetic_contradiction_privacy_0001.txt": 3,
        "synthetic_dangling_multipart_0001.txt": 4,
        "synthetic_entropy_openended_0001.txt": 3,
    }
    for name, expected in expected_counts.items():
        transcript = (samples_dir / name).read_text(encoding="utf-8")
        steps = parse_transcript(transcript)
        assert len(steps) == expected, name


def test_parse_marks_unsupported_terminal_as_conclusion(samples_dir) -> None:
    transcript = (samples_dir / "synthetic_unsupported_terminal_0001.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)
    assert len(steps) == 1
    assert steps[0].step_type == "conclusion"
