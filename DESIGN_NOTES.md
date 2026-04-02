# trace-topology: Design Notes

Captured from the founding conversation, April 2, 2026. This document is the primary context for an agent session to generate a build plan.

## What This Is

A post-hoc debugger for LLM reasoning traces. Takes a raw chain-of-thought transcript and maps its logical topology — the dependency graph between claims, the bond types between reasoning steps, and the structural failure modes (circular reasoning, unsupported leaps, contradictions, abandoned threads). Rendered in the terminal as ASCII directed graphs.

No API calls needed to run. Works on any CoT dump from any model. Python. Terminal-native.

## The Gap

Existing tools treat reasoning as a **process to steer** (Tree-of-Thought, Graph-of-Thought, Hippo, ReasonGraph). They run during inference. They're browser-based research demos.

This tool treats reasoning as a **program to debug**. It runs after the fact, on transcripts. Different verb, different tool.

The academic framing exists — especially the ByteDance paper "The Molecular Structure of Thought" (arXiv 2601.06002, Jan 2026) — but no practical tool occupies this space.

## Theoretical Foundation

The ByteDance paper models long CoT as molecular structures with three bond types:

- **Covalent bonds** (deep reasoning): strong logical dependencies where one claim directly supports another
- **Hydrogen bonds** (self-reflection): steps where the model reviews or corrects its own prior reasoning
- **Van der Waals forces** (self-exploration): weak associative connections, tangential exploration

Key findings from the paper:
- Effective reasoning traces have stable molecular-like structures
- Structural anomalies (broken bonds, missing connections, loops) correlate with reasoning failures
- "Semantic isomers" exist: structurally different traces that reach the same correct conclusion
- Only bonds that promote fast entropy convergence support stable reasoning
- Structural competition between bond types impairs training

If long CoT has stable structural patterns, then structural anomalies should be detectable. That's the core hypothesis.

## Prior Art Surveyed

| Tool/Paper | What it does | How we differ |
|---|---|---|
| Landscape of Thoughts | t-SNE visualization of reasoning states | We map logical structure, not embedding space |
| ReasonGraph | Flowchart illustration of reasoning methods | We find where structure breaks, not just what it looks like |
| Hippo | Interactive tree-based reasoning steering | We're post-hoc, not interactive; terminal, not browser |
| Topologies of Reasoning (ETH Zürich) | Categorizes CoT/ToT/GoT as structural patterns | We implement detection, not just taxonomy |
| Molecular Structure of Thought (ByteDance) | Maps CoT as molecular bonds | We build the tool that uses their framework as a debugger |
| CRV (Computational Graph Verification) | Attribution graphs for step correctness | They need model internals; we work on text transcripts alone |

## Design Principles

Drawn from the Stack Research body of work:

1. **Structure over language.** Output is graphs and artifacts, not prose. (from "AI That Refuses to Predict")
2. **The trace is the thought.** We don't claim to analyze "thinking" — we analyze the text artifact. The text is what we have. (from "The Unaskable Question Machine": "There is no thought that precedes the text. The text is the thought.")
3. **Terminal-native.** ASCII art > CSS. The interface is the terminal. (user preference)
4. **No API calls for analysis.** The tool runs on transcripts. LLM backends are optional, for enhanced classification only.
5. **Inspectable artifacts.** Every analysis step produces a machine-readable intermediate (JSON). Every graph has a data representation underneath the ASCII rendering.

## Architecture (Proposed)

```
trace-topology/
  src/
    parser/         — segment a raw CoT transcript into logical steps
    graph/          — build dependency graph between steps, classify bond types
    analysis/       — detect failure modes (cycles, dangling nodes, contradictions)
    render/         — ASCII graph rendering for terminal output
  cli.py            — entry point
  tests/
  data/
    samples/        — example CoT transcripts for testing
  README.md
  AGENTS.md
```

### Pipeline

```
raw transcript → parse into steps → build dependency graph → classify bonds → detect anomalies → render
```

1. **Parser**: Segment a reasoning trace into discrete logical steps. Handle varied formats (thinking blocks, numbered steps, free-form prose). Each step becomes a node.

2. **Graph builder**: Determine dependencies between steps. Which claims support which conclusions? Where does the model reference its own prior reasoning? This produces a directed graph with typed edges (covalent/hydrogen/van der Waals, borrowing from the ByteDance framework).

3. **Analyzer**: Walk the graph looking for structural problems:
   - **Cycles**: circular reasoning (A supports B supports A)
   - **Dangling nodes**: claims with no support and no dependents (abandoned threads)
   - **Unsupported leaves**: final conclusions that trace back to unsupported assertions
   - **Contradiction pairs**: nodes that assert X and not-X
   - **Entropy divergence**: sections where the reasoning gets less focused over time (measurable via information density)
   - **Bond imbalance**: too much self-reflection without deep reasoning, or too much exploration without convergence

4. **Renderer**: ASCII directed graph in the terminal. Color-coded by bond type. Failure modes highlighted. Summary statistics.

## Open Questions

- How do we segment free-form reasoning into discrete steps? Sentence boundaries are too granular. Paragraph breaks are too coarse. Some heuristic around logical transitions ("therefore", "but", "wait", "actually", "let me reconsider") may work as a starting point.
- Should bond classification use an LLM, or can we do it with heuristics? Start with heuristics. Add optional LLM judge later (same pattern as the Unaskable Question Machine).
- What's the right graph layout algorithm for ASCII rendering? Sugiyama (layered) is standard for DAGs. Libraries like `grandalf` exist in Python.
- How do we handle very long traces (10k+ tokens)? Probably need a hierarchical view — cluster steps into "phases" first, then drill into individual phase topology.

## Naming

The name `trace-topology` was chosen deliberately:
- **trace**: honest about what the input is — a recording, not thought itself
- **topology**: the mathematical study of shape and connectivity, which is exactly what we map
- No metaphor. No brand. Says what it does.

## Connections to Other Stack Research Projects

- **deterministic-compiler-for-thought**: DCT compiles thought specs into deterministic artifacts. trace-topology could consume DCT's IR as structured input, or DCT could use trace-topology to validate that compiled reasoning has sound structure.
- **the-unaskable-question-machine**: UQM probes where models break. trace-topology analyzes HOW they break in extended reasoning. UQM transcripts (especially "cracks") are ideal test inputs.
- **genetic-prompt-programming**: GPP evolves prompts. trace-topology could serve as a fitness signal — prompts that produce better-structured reasoning score higher.
- **executable-metaphors**: Both projects treat text artifacts as the source of truth to be compiled/analyzed.
