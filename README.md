# trace-topology

A post-hoc debugger for LLM reasoning traces. Takes a raw chain-of-thought transcript, maps its logical topology as a directed graph, classifies bond types between reasoning steps, and finds where the structure broke.

Existing tools treat reasoning as a process to steer. This treats it as a program to debug.

## The idea

The ByteDance paper "The Molecular Structure of Thought" (arXiv 2601.06002) showed that effective long chain-of-thought reasoning forms stable molecular-like structures with three bond types: covalent (deep reasoning), hydrogen (self-reflection), and van der Waals (exploration). Structural anomalies correlate with reasoning failures.

trace-topology takes that framework and builds a debugger around it. Feed it a transcript. It parses the reasoning into steps, builds a dependency graph, classifies the bonds, and reports what broke: circular reasoning, abandoned threads, unsupported conclusions, contradictions, entropy divergence.

Output is an ASCII directed graph in the terminal with a JSON artifact underneath.

## Requirements

- Python 3.11+
- No API calls needed for core analysis
- Optional: [Ollama](https://ollama.com) for LLM-assisted bond classification

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

The Makefile targets (`make install`, `make test`, `make lint`) still work if you prefer a local `.venv` and `pip install -e ".[dev]"`. Add backend extras explicitly when needed, for example `pip install -e ".[dev,ollama]"` or `pip install -e ".[dev,anthropic]"`.

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

# Pipe from stdin
cat thinking_block.txt | tt analyze -

# CI-style gate: exit 1 when the report lists any structural findings
tt analyze transcript.txt --fail-on-findings

# Evaluate against golden annotations
tt eval --annotations data/samples/golden --samples data/samples --out eval.json

# Fail the command when average golden metrics drop (optional floors)
tt eval --annotations data/samples/golden --samples data/samples \
  --min-avg-bond-precision 0.8 \
  --min-avg-bond-recall 0.88 \
  --min-avg-finding-precision 0.8 \
  --min-avg-finding-recall 0.75
```

Exit codes: by default commands exit `0`. Use `--fail-on-findings` on `tt analyze` or `--min-avg-*` on `tt eval` to return `1` when gates fail (for CI).

Rendering adapts automatically: traces under 15 steps keep the full step-by-step adjacency view, while larger traces switch to a compact phase summary with aggregated phase links. `tt analyze` adds finding-local hotspot neighborhoods in that compact mode.

Machine-readable outputs follow the v1 contract in [docs/ARTIFACT_CONTRACT.md](docs/ARTIFACT_CONTRACT.md). Breaking JSON changes must bump the schema version and be called out there.

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

If an optional backend dependency is missing, the CLI now fails with an install hint instead of silently falling back.

## Example Sessions

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

Optional harvest flow:

```bash
uv sync --extra dev --extra ollama
make harvest-cycles
tt analyze data/samples/deepseek-r1-8b_circular_closed_loop_20260402.txt \
  --out analysis.closed-loop.json
tt eval --annotations data/samples/golden --samples data/samples
```

What to expect:

- the harvest step writes transcript `.txt` files and paired metadata `.json` files into `data/samples/`
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

## v0.1 Status

### What works

- End-to-end local pipeline is operational: harvest -> parse -> graph -> analyze -> ASCII render.
- JSON artifacts are emitted at every stage and can be evaluated against golden annotations.
- JSON artifacts now carry a versioned top-level contract (`artifact_type`, `schema_version = 1`) documented in `docs/ARTIFACT_CONTRACT.md`.
- Real transcript harvesting works via Ollama (`llama3.1:8b`, `deepseek-r1:8b` used in calibration).
- Cycle detection is confirmed on a real harvested closed-loop trace (`deepseek-r1-8b_circular_closed_loop_20260402.txt`).
- Self-correction arithmetic traces are calibrated so the clean DeepSeek handshake trace produces no findings and the flawed Llama handshake trace collapses to a single unsupported-terminal finding.
- Cycle calibration now covers repo-local implicit and explicit loops: `synthetic_cycle_trust_0001`, `deepseek-r1-8b_circular_closed_loop_20260402`, `deepseek-r1-8b_circular_trust_20260402`, and `llama3.1-8b_circular_trust_20260402`.
- Golden-set regression harness is in place and run continuously during graph calibration.
- Current golden baseline (`tt eval --annotations data/samples/golden --samples data/samples`) is:
  - `count = 11`
  - `avg_bond_precision = 0.924`
  - `avg_bond_recall = 0.955`
  - `avg_finding_precision = 1.000`
  - `avg_finding_recall = 1.000`

### Known limitations

- **Detectors / findings:** Heuristic-based; behavior is regression-tested on golden fixtures, but long free-form traces can still produce false positives or false negatives.
- **Graph / bonds:** Support edges are stronger on the current gold set, real arithmetic traces, and the calibrated cycle corpus, but a common failure mode is still **bad step boundaries**, not only missing links in linear prose. Format cues (headings, labels, discourse markers) still help.
- The parser treats triple-backtick fenced code blocks, markdown headings, and `<think>` / `<thinking>` blocks as atomic regions to reduce over-segmentation.
- ASCII rendering now adapts for large traces with phase summaries and finding-local hotspots, but it is still a compression layer rather than a full graph-layout system.
- Optional backend-assisted bond judging is available for `tt graph` and `tt analyze` (`--backend none|ollama|anthropic`); it is not required for the local core pipeline.
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
