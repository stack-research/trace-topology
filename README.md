# trace-topology

A post-hoc debugger for LLM reasoning traces. Takes a raw chain-of-thought transcript, maps its logical topology as a directed graph, classifies bond types between reasoning steps, and finds where the structure broke.

Existing tools treat reasoning as a process to steer. This treats it as a program to debug.

## What this does for you

When an LLM or coding agent gives you a long reasoning transcript and the final answer feels wrong, `trace-topology` helps you answer a simpler question: where did the reasoning break?

Instead of rereading the whole trace by hand, you get a structural readout:

- loops where the model uses its own conclusion as support
- abandoned branches that never reconnect
- conclusions that appear without traced support
- contradictions and drift

The tool works on local transcript files. Output stays in the terminal as ASCII plus JSON artifacts underneath.

For a runnable developer-first example, see [docs/FIRST_DEBUG_SESSION.md](docs/FIRST_DEBUG_SESSION.md).

## Simple Use Cases

Reach for `trace-topology` when:

- an agent proposes a patch, revert, or root-cause claim, but the reasoning feels off
- the reasoning stream flashed by too fast to read, and now you only remember the final answer
- a long agent run kept revising its plan and you want to see where it started looping
- you suspect stale memory, prompt poisoning, or policy drift shaped the final move
- you want a post-mortem artifact for an agent failure, not just the final diff

Do not use it when:

- you only need the model's final answer, not its reasoning trace
- the transcript is too short to contain meaningful structure
- you need semantic truth guarantees; this tool is a debugger for trace shape, not an oracle

## Quickstart

Install the local core path:

```bash
uv sync --extra dev
```

If you already have a transcript file, run:

```bash
tt analyze transcript.txt
```

If your agent prints its reasoning too fast to read live, save the stream first and inspect it after the run.

Examples:

```bash
# If the agent writes to stdout/stderr in your terminal
your-agent-command 2>&1 | tee transcript.txt

# On macOS/Linux, capture the whole terminal session
script -q transcript.txt your-agent-command
```

Then point `trace-topology` at the saved plaintext file:

```bash
tt analyze transcript.txt
```

Read the findings like this:

- `cycle`: the trace starts using its own conclusion as evidence
- `unsupported_terminal`: the final answer appears without enough traced support
- `dangling`: the model opened a branch and never brought it back

If you want one concrete session you can run right now, use:

```bash
tt analyze data/samples/synthetic_agent_cycle_debug_0001.txt
```

## The idea

The ByteDance paper "The Molecular Structure of Thought" (arXiv 2601.06002) showed that effective long chain-of-thought reasoning forms stable molecular-like structures with three bond types: covalent (deep reasoning), hydrogen (self-reflection), and van der Waals (exploration). Structural anomalies correlate with reasoning failures.

trace-topology takes that framework and builds a debugger around it. Feed it a transcript. It parses the reasoning into steps, builds a dependency graph, classifies the bonds, and reports what broke: circular reasoning, abandoned threads, unsupported conclusions, contradictions, entropy divergence.

Output is an ASCII directed graph in the terminal with a JSON artifact underneath.

## Requirements

- Python 3.11+
- No API calls needed for core analysis
- Optional: [Ollama](https://ollama.com), [Anthropic](https://www.anthropic.com/api), or [OpenAI](https://platform.openai.com/docs/overview) for LLM-assisted bond classification

## Install

Core local install, no network backends:

```bash
uv sync --extra dev
```

Core plus Ollama support:

```bash
uv sync --extra dev --extra ollama
```

Core plus Anthropic support:

```bash
uv sync --extra dev --extra anthropic
```

Core plus OpenAI support:

```bash
uv sync --extra dev --extra openai
```

Everything optional:

```bash
uv sync --extra dev --extra all
```

The base install is the zero-network core path. `tt parse`, `tt graph --backend none`, `tt analyze --backend none`, and `tt eval` should work without optional backend packages.

## Development

With [uv](https://docs.astral.sh/uv/) installed:

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format .   # optional
uv run pytest -q
```

The Makefile targets (`make install`, `make test`, `make lint`) still work if you prefer a local `.venv` and `pip install -e ".[dev]"`. Add backend extras explicitly when needed, for example `pip install -e ".[dev,ollama]"`, `pip install -e ".[dev,anthropic]"`, or `pip install -e ".[dev,openai]"`.

## Usage

```bash
# Analyze a reasoning transcript
tt analyze transcript.txt

# Parse into steps only
tt parse transcript.txt --out steps.json

# Build graph only
tt graph transcript.txt --out graph.json

# Use LLM-assisted bond classification
tt analyze transcript.txt --backend ollama --model llama3.1:8b
tt analyze transcript.txt --backend openai --model gpt-5-mini

# Pipe from stdin
cat thinking_block.txt | tt analyze -

# CI-style gate: exit 1 when the report lists any structural findings
tt analyze transcript.txt --fail-on-findings

# Fail only on findings at or above a chosen severity
tt analyze transcript.txt --fail-on-min-severity severe

# Fail only on findings at or above a score threshold
tt analyze transcript.txt --fail-on-min-score 0.8

# Evaluate against golden annotations
tt eval --annotations data/samples/golden --samples data/samples --out eval.json

# Fail the command when average golden metrics drop (optional floors)
tt eval --annotations data/samples/golden --samples data/samples \
  --min-avg-bond-precision 0.8 \
  --min-avg-bond-recall 0.88 \
  --min-avg-finding-precision 0.8 \
  --min-avg-finding-recall 0.75
```

Exit codes: by default commands exit `0`. Use `--fail-on-findings`, `--fail-on-min-severity`, or `--fail-on-min-score` on `tt analyze`, or `--min-avg-*` on `tt eval`, to return `1` when gates fail (for CI).

Rendering adapts automatically: traces under 15 steps keep the full step-by-step adjacency view, while larger traces switch to a compact phase summary with aggregated phase links. `tt analyze` adds finding-local hotspot neighborhoods in that compact mode.

Machine-readable outputs follow the v1 contract in [docs/ARTIFACT_CONTRACT.md](docs/ARTIFACT_CONTRACT.md). Breaking JSON changes must bump the schema version and be called out there.

## Finding priority

`tt analyze` now ranks findings in a stable order in both terminal output and JSON.

Severity scale:

- `low`
- `moderate`
- `severe`

Ranking order:

1. higher severity
2. higher score
3. finding-type priority
4. earlier involved step

The `analysis.findings` array is highest-priority first. The report also prints a `finding-summary:` line with counts by severity and the current top finding type.

## Parser behavior

Step segmentation is heuristic. The parser prefers structure when it sees it:

- numbered and bulleted lists
- markdown headings
- `P1:` style labeled points
- `<think>` / `<thinking>` blocks
- triple-backtick fenced code blocks

Atomic regions:

- fenced code blocks are kept intact
- `<think>` / `<thinking>` regions are treated as bounded blocks

Large prose traces are usually split by paragraph before finer transition markers are used. Short lead-in lines can be merged with nearby equation or result lines to avoid trivial one-line arithmetic steps.

Known failure modes:

- long free-form prose can still merge steps that a human would separate
- terse line-broken traces can still over-segment when formatting cues are weak
- verification tails and boxed answers are handled better than before, but still need human judgment on messy traces

## Backend guidance

Recommended default: `--backend none`.

- Use `--backend none` for CI, eval, regression work, and reproducible local analysis.
- Use `--backend ollama` when bond typing on ambiguous prose is worth an extra local judge.
- Use `--backend anthropic` only when you explicitly want an external higher-cost judge; it is not the default path.
- Use `--backend openai` when you want an external judge through the official OpenAI SDK; it is optional, credentialed, and not the default path.

If an optional backend dependency is missing, the CLI now fails with an install hint instead of silently falling back.

## Example Sessions

Start here if you want a plain-English developer walkthrough:

- [docs/FIRST_DEBUG_SESSION.md](docs/FIRST_DEBUG_SESSION.md)

Sample-file flow:

```bash
tt parse data/samples/deepseek-r1-8b_self_correction_handshake_20260402.txt \
  --out steps.handshake.json

tt graph data/samples/deepseek-r1-8b_self_correction_handshake_20260402.txt \
  --out graph.handshake.json

tt analyze data/samples/deepseek-r1-8b_self_correction_handshake_20260402.txt \
  --out analysis.handshake.json

tt eval --annotations data/samples/golden --samples data/samples \
  --out eval.json
```

What to expect:

- `steps.handshake.json`, `graph.handshake.json`, `analysis.handshake.json`, and `eval.json` all include `artifact_type` and `schema_version`
- `tt graph` prints either the full adjacency view or the compact phase view, depending on trace size
- `tt analyze` prints findings or `hotspots: none` for a clean trace
- `tt eval` prints the summary block used for regression gates
- the walkthrough sample at `data/samples/synthetic_agent_cycle_debug_0001.txt` produces a real `cycle` finding and is explained in `docs/FIRST_DEBUG_SESSION.md`

Optional harvest flow:

```bash
uv sync --extra dev --extra ollama
make harvest-cycles
make harvest-uqm
tt analyze data/samples/deepseek-r1-8b_circular_closed_loop_20260402.txt \
  --out analysis.closed-loop.json
tt eval --annotations data/samples/golden --samples data/samples
```

What to expect:

- the harvest step writes transcript `.txt` files and paired metadata `.json` files into `data/samples/`
- `make harvest-uqm` imports the curated pathological crack slice from the sibling `../the-unaskable-question-machine/data` repo when it is present locally
- the analysis step emits an analysis artifact and a readable ASCII report
- the eval step confirms whether the current calibrated corpus still clears the metric floors

## What it detects

| Failure mode | What it means |
|---|---|
| Cycles | Circular reasoning: A supports B supports A |
| Dangling nodes | Abandoned threads: claims with no support and no dependents |
| Unsupported terminals | Conclusions that trace back to unsupported assertions |
| Contradiction pairs | Steps that assert X and not-X |
| Bond imbalance | Too much reflection without reasoning, or exploration without convergence |
| Entropy divergence | Reasoning that gets less focused over time |

## Pipeline

```
raw transcript → parse into steps → build dependency graph → classify bonds → detect anomalies → render
```

Each stage produces a JSON artifact. Stages can be run independently.

## v0.2 Status

### What works

- End-to-end local pipeline is operational: harvest -> parse -> graph -> analyze -> ASCII render.
- JSON artifacts are emitted at every stage and can be evaluated against golden annotations.
- JSON artifacts now carry a versioned top-level contract (`artifact_type`, `schema_version = 1`) documented in `docs/ARTIFACT_CONTRACT.md`.
- Real transcript harvesting works via Ollama (`llama3.1:8b`, `deepseek-r1:8b` used in calibration).
- Cycle detection is confirmed on a real harvested closed-loop trace (`deepseek-r1-8b_circular_closed_loop_20260402.txt`).
- Self-correction arithmetic traces are calibrated so the clean DeepSeek handshake trace produces no findings and the flawed Llama handshake trace collapses to a single unsupported-terminal finding.
- Clean real probability traces are now in gold for both DeepSeek and Llama, expanding the no-finding control set beyond the handshake corpus.
- Cycle calibration now covers repo-local implicit and explicit loops: `synthetic_cycle_trust_0001`, `deepseek-r1-8b_circular_closed_loop_20260402`, `deepseek-r1-8b_circular_trust_20260402`, and `llama3.1-8b_circular_trust_20260402`.
- Real circular coverage now also includes `llama3.1-8b_circular_free_will_20260402` as a light pathological long-form case.
- The last remaining real closed-loop Llama trace is now in gold as `llama3.1-8b_circular_closed_loop_20260402`.
- The corpus path now includes a tested UQM import flow and curated pathological crack samples under `data/samples/`.
- Golden-set regression harness is in place and run continuously during graph calibration.
- Current golden baseline (`tt eval --annotations data/samples/golden --samples data/samples`) is:
  - `count = 19`
  - `avg_bond_precision = 0.956`
  - `avg_bond_recall = 0.974`
  - `avg_finding_precision = 1.000`
  - `avg_finding_recall = 1.000`

### Known limitations

- **Detectors / findings:** Heuristic-based; behavior is regression-tested on golden fixtures, but long free-form traces can still produce false positives or false negatives.
- **Graph / bonds:** Support edges are stronger on the current gold set, real arithmetic traces, and the calibrated cycle corpus, but a common failure mode is still **bad step boundaries**, not only missing links in linear prose. Format cues (headings, labels, discourse markers) still help.
- The core is being treated as stable at `v0.2`; remaining backlog items are mostly parser granularity, packaging polish, library API, and future corpus growth.
- The parser treats triple-backtick fenced code blocks, markdown headings, and `<think>` / `<thinking>` blocks as atomic regions to reduce over-segmentation.
- ASCII rendering now adapts for large traces with phase summaries and finding-local hotspots, but it is still a compression layer rather than a full graph-layout system.
- Optional backend-assisted bond judging is available for `tt graph` and `tt analyze` (`--backend none|ollama|anthropic|openai`); it is not required for the local core pipeline.
- The base install is core-only; backend packages are optional extras.

### Repro for current milestone

```bash
# Set up and validate
make venv
make install
make test
make eval

# Render the closed-loop cycle trace used in calibration
make graph-cycle
make analyze-cycle
```

## Related

- [The Molecular Structure of Thought](https://arxiv.org/abs/2601.06002) — theoretical foundation
- [The Unaskable Question Machine](https://github.com/stack-research/the-unaskable-question-machine) — sibling project; its "crack" responses are ideal test inputs
- [Genetic Prompt Programming](https://github.com/stack-research/genetic-prompt-programming) — trace-topology could serve as a fitness signal for prompt evolution
