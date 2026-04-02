# AGENTS Guidance for trace-topology

A post-hoc debugger for LLM reasoning traces. Parses chain-of-thought transcripts into directed graphs, classifies bond types between reasoning steps, and detects structural failure modes.

## Read First

Read `DESIGN_NOTES.md` before writing any code. It contains the full design conversation, architecture, theoretical foundation, and open questions.

Read `DEVELOPER_CHECKLIST.md` for the living backlog of work needed to make the project genuinely useful to developers (parser, graph, detectors, DX, data). **Keep it updated** when you complete items, change priorities, or discover new gaps—same as `README.md` and this file (`AGENTS.md`): if your change affects what users or agents should expect, update the relevant doc.

## Hard Rules

- Python 3.11+. No other runtime.
- Terminal-native. No web UI, no browser, no HTML output.
- Core analysis requires zero API calls and zero network access. The tool works on local transcript files only.
- Optional LLM-assisted classification (Ollama default, Anthropic optional) follows the same backend pattern as `../the-unaskable-question-machine/`.
- All intermediate representations are JSON. Every analysis step writes a machine-readable artifact.
- ASCII rendering only. No image generation for graphs.

## Project Structure

```
src/
  trace_topology/
    __init__.py
    parser.py       — segment transcripts into logical steps (nodes)
    graph.py        — build dependency graph, classify edge/bond types
    analysis.py     — detect structural failure modes
    render.py       — ASCII directed graph rendering
    models.py       — dataclasses for steps, edges, graphs, findings
cli.py              — click-based CLI entry point
tests/
  test_parser.py
  test_graph.py
  test_analysis.py
  test_render.py
  conftest.py
data/
  samples/          — example CoT transcripts for development and testing
pyproject.toml
```

## Development Conventions

- Follow existing Stack Research patterns: `uv` for dependency management, `ruff` for linting/formatting, `pytest` for tests.
- Favor clarity over abstraction. This is research code.
- Each module should be independently testable.
- Log liberally. The interesting findings will be in edge cases.
- Keep external dependencies minimal. `click` for CLI, `grandalf` or similar for graph layout. Avoid heavy frameworks.

## Pipeline

```
raw transcript → parse → graph → analyze → render
```

Each stage reads the previous stage's output and writes its own JSON artifact. The CLI orchestrates the pipeline but individual stages can be run independently.

## Bond Type Classification

Follows the ByteDance "Molecular Structure of Thought" framework (arXiv 2601.06002):

- **Covalent** (deep reasoning): step B logically depends on step A. "Therefore", "because", "given that".
- **Hydrogen** (self-reflection): step B reviews or corrects step A. "Wait", "actually", "let me reconsider", "that's wrong".
- **Van der Waals** (exploration): step B is loosely associated with step A. Tangential, not dependent.

Start with heuristic keyword/pattern matching. Add optional LLM judge later.

## Failure Modes to Detect

- Cycles (circular reasoning)
- Dangling nodes (abandoned threads)
- Unsupported terminal nodes (conclusions without traced support)
- Contradiction pairs (X and not-X)
- Bond imbalance (all reflection, no reasoning; all exploration, no convergence)
- Entropy divergence (reasoning that gets less focused over time)

## Testing

- Use real CoT transcripts as golden test fixtures in `data/samples/`.
- Good sources: Claude thinking blocks, DeepSeek-R1 reasoning traces, o1-style CoT dumps.
- The Unaskable Question Machine's "crack" responses (in `../the-unaskable-question-machine/`) are ideal pathological test cases.
- Parser tests should cover: numbered step lists, free-form prose, thinking block XML, mixed formats.
- Analysis tests should include known-good and known-broken reasoning traces.

## CLI Interface

```bash
# Analyze a transcript file
tt analyze transcript.txt

# Parse only (emit step JSON)
tt parse transcript.txt --out steps.json

# Graph only (emit graph JSON)
tt graph transcript.txt --out graph.json

# Use LLM-assisted classification
tt analyze transcript.txt --backend ollama --model llama3.1:8b

# Pipe from stdin
cat transcript.txt | tt analyze -

# CI gate: non-zero exit if any findings
tt analyze transcript.txt --fail-on-findings

# Golden eval with optional metric floors (non-zero if below)
tt eval --annotations data/samples/golden --samples data/samples --min-avg-bond-recall 0.4
```
