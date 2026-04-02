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

# Evaluate against golden annotations
tt eval --annotations data/samples/golden --samples data/samples --out eval.json
```

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
- Real transcript harvesting works via Ollama (`llama3.1:8b`, `deepseek-r1:8b` used in calibration).
- Cycle detection is confirmed on a real harvested closed-loop trace (`deepseek-r1-8b_circular_closed_loop_20260402.txt`).
- Golden-set regression harness is in place and run continuously during graph calibration.

### Known limitations

- Bond classification is still heuristic-heavy; contradiction and entropy findings are noisy on long prose traces.
- Graph connectivity depends on format cues (e.g., headings, labels, discourse markers). Some linear prose still under-links.
- ASCII rendering is functional but not yet optimized for very large traces (layout compression and emphasis still basic).
- Optional backend-assisted bond judging is available for `tt graph` and `tt analyze`, but it is not required for the local core pipeline.

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
