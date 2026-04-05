from __future__ import annotations

import pytest

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


def test_parse_terse_linebreak_prose_not_oversegmented(samples_dir) -> None:
    """Short lines without list markers should not become one step per line."""
    transcript = (samples_dir / "terse_linebreak_prose_0001.txt").read_text(encoding="utf-8")
    steps = parse_transcript(transcript)
    assert len(steps) <= 2, f"expected merged steps, got {len(steps)}"


def test_parse_marks_unsupported_terminal_as_conclusion(samples_dir) -> None:
    transcript = (samples_dir / "synthetic_unsupported_terminal_0001.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)
    assert len(steps) == 1
    assert steps[0].step_type == "conclusion"


def test_parse_code_fence_mixed_not_oversegmented(samples_dir) -> None:
    transcript = (samples_dir / "parser_code_fence_mixed_0001.txt").read_text(encoding="utf-8")
    steps = parse_transcript(transcript)

    # Expected segmentation under the list-marker heuristic:
    # 1) setup line, code fence as one atomic step, 2) conclusion line.
    assert len(steps) == 3

    fence_steps = [step for step in steps if "```python" in step.text]
    assert len(fence_steps) == 1
    assert "- bullet inside code" in fence_steps[0].text
    assert "P2: internal point reference" in fence_steps[0].text

    bullet_steps = [step for step in steps if "- bullet inside code" in step.text]
    assert len(bullet_steps) == 1

    assert steps[-1].step_type == "conclusion"


def test_parse_headings_mixed_sections(samples_dir) -> None:
    transcript = (samples_dir / "parser_headings_mixed_0001.txt").read_text(encoding="utf-8")
    steps = parse_transcript(transcript)

    # Expected: one step per structural line (list marker or markdown headings).
    assert len(steps) == 3

    joined = "\n".join(step.text for step in steps)
    assert "# Section A" in joined
    assert "# Section B" in joined


def test_parse_mixed_fence_thinking_combination(samples_dir) -> None:
    transcript = (samples_dir / "parser_mixed_fence_thinking_0001.txt").read_text(encoding="utf-8")
    steps = parse_transcript(transcript)

    # Expected segmentation:
    # 1) setup line, code fence atomic step, thinking atomic step, 2) conclusion line.
    assert len(steps) == 4

    fence_steps = [step for step in steps if "```text" in step.text]
    assert len(fence_steps) == 1
    assert "P2: internal point reference" in fence_steps[0].text

    thinking_steps = [step for step in steps if "<thinking>" in step.text]
    assert len(thinking_steps) == 1
    assert "wait actually P1 implies P2" in thinking_steps[0].text
    assert "# inner heading inside thinking" in thinking_steps[0].text

    assert steps[-1].step_type == "conclusion"
    assert thinking_steps[0].step_type in {"correction", "derivation"}


def test_parse_deepseek_handshake_matches_calibrated_shape(samples_dir) -> None:
    transcript = (samples_dir / "deepseek-r1-8b_self_correction_handshake_20260402.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)

    assert len(steps) == 7
    assert steps[-1].text == "\\boxed{13}"
    assert "degree sum approach also confirms this" in steps[-2].text.lower()


def test_parse_llama_handshake_merges_short_result_lines(samples_dir) -> None:
    transcript = (samples_dir / "llama3.1-8b_self_correction_handshake_20260402.txt").read_text(
        encoding="utf-8"
    )
    steps = parse_transcript(transcript)

    assert len(steps) == 9
    assert "28 - 3 = 25" in steps[-2].text
    assert steps[-1].step_type == "conclusion"


def test_parse_invalid_granularity_fails_fast() -> None:
    with pytest.raises(ValueError, match="Unsupported parser granularity"):
        parse_transcript("Claim. Therefore conclusion.", granularity="token")


def test_paragraph_mode_is_coarser_than_sentence_mode_on_long_prose(samples_dir) -> None:
    transcript = (samples_dir / "synthetic_contradiction_privacy_0001.txt").read_text(encoding="utf-8")

    paragraph_steps = parse_transcript(transcript, granularity="paragraph")
    sentence_steps = parse_transcript(transcript, granularity="sentence")

    assert len(paragraph_steps) <= len(sentence_steps)
    assert len(paragraph_steps) == 1
    assert len(sentence_steps) == 3


def test_sentence_mode_splits_terse_prose_more_finely(samples_dir) -> None:
    transcript = (samples_dir / "terse_linebreak_prose_0001.txt").read_text(encoding="utf-8")

    paragraph_steps = parse_transcript(transcript, granularity="paragraph")
    sentence_steps = parse_transcript(transcript, granularity="sentence")

    assert len(paragraph_steps) == 1
    assert len(sentence_steps) == 4


def test_sentence_mode_keeps_atomic_regions_intact(samples_dir) -> None:
    transcript = (samples_dir / "parser_mixed_fence_thinking_0001.txt").read_text(encoding="utf-8")

    steps = parse_transcript(transcript, granularity="sentence")

    assert len(steps) == 4
    assert sum("```text" in step.text for step in steps) == 1
    assert sum("<thinking>" in step.text for step in steps) == 1


def test_sentence_mode_preserves_merge_heuristics_for_short_leadin_and_boxed_answer() -> None:
    transcript = "Therefore we compute:\n28 - 3 = 25\n\\boxed{25}"

    steps = parse_transcript(transcript, granularity="sentence")

    assert len(steps) == 1
    assert "28 - 3 = 25" in steps[0].text
    assert "\\boxed{25}" in steps[0].text


def test_sentence_mode_preserves_merge_heuristics_for_result_and_boxed_answer() -> None:
    transcript = "28 - 3 = 25\n\\boxed{25}"

    steps = parse_transcript(transcript, granularity="sentence")

    assert len(steps) == 1
    assert steps[0].text == "28 - 3 = 25\n\\boxed{25}"


def test_sentence_mode_preserves_merge_heuristics_for_verification_tail() -> None:
    transcript = "28 - 3 = 25\nThis means the condition that matters is satisfied.\n\\boxed{25}"

    steps = parse_transcript(transcript, granularity="sentence")

    assert len(steps) == 2
    assert "This means the condition that matters is satisfied." in steps[0].text
    assert steps[1].text == "\\boxed{25}"
