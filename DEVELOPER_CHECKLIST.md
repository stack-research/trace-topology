# Developer checklist — making trace-topology broadly useful

This file tracks **what still needs doing** so the project is genuinely useful to developers debugging real LLM traces—not just a research prototype. Treat it as a living backlog: **update it** when you finish items, reprioritize, or discover new gaps.

Use `- [ ]` for open work and `- [x]` for done when you edit this file.

---

## Parser (step segmentation)

- [ ] Reduce **over-segmentation** on terse, line-broken traces (e.g. some harvested Llama-style handshakes).
- [ ] Solid coverage for **mixed formats**: numbered lists, markdown headings, thinking blocks, code-heavy traces.
- [ ] Optional **configurable granularity** (sentence vs paragraph vs heuristic) for power users.
- [ ] Document parser behavior and failure modes in `README.md` or a short `docs/` note.

## Graph (support links and bond typing)

- [ ] Continue improving **support-link construction** on real traces where steps are right but edges were thin.
- [ ] Calibrate **bond type** heuristics against more hand-annotated gold (not only synthetic).
- [ ] Clear rules for when **optional backends** (`--backend ollama|anthropic`) help vs add noise; document defaults.

## Analysis (detectors)

- [ ] Keep **contradiction / entropy** precise on long prose without tanking recall on gold.
- [ ] **Cycle detection**: validate on diverse real cyclic traces, not only closed-loop prompts.
- [ ] Consider **severity tuning** or ranking so the CLI surfaces the most actionable findings first.

## Rendering and CLI

- [ ] **ASCII layout** for large traces: compression, grouping, or phase summaries so output stays readable in a normal terminal.
- [ ] **Stable JSON schemas** across versions; document breaking changes in `README.md`.
- [ ] **Exit codes** (e.g. non-zero when structural failures exceed a threshold) for CI integration.
- [ ] Keep **CLI/docs/examples aligned**: when flags or commands change, update `README.md` and `AGENTS.md` in the same pass; keep smoke tests for documented CLI surfaces.

## Developer experience

- [ ] **CI** (lint + tests on push/PR) if the repo is public or multi-contributor.
- [ ] **Pre-commit** or documented `make`/`uv` one-liners for format + test before commit.
- [ ] **Example sessions** in `README.md`: harvest → analyze → eval on a sample file.
- [ ] Optional **packaging** polish: `pip install`/Homebrew story if adoption matters.
- [ ] Preserve the **zero-network core path**: parse/graph/analyze should still work when optional backend dependencies are not installed.

## Data and evaluation

- [ ] Grow **golden annotations** for real traces (hand-reviewed or assisted + corrected).
- [ ] **Regression gates**: `tt eval` summary thresholds or trend notes in this checklist.
- [ ] **UQM / external corpus** import path documented and tested when data is available.

## Ecosystem (later, if desired)

- [ ] Editor or **LSP** integration (jump to step from finding)—only if terminal-first scope expands.
- [ ] **Stable library API** (`import trace_topology`) for embedding in other tools—document supported surfaces.

---

## How to use this file

1. Before a focused sprint, pick a section and move the top items into issues or commits.
2. After a merge that advances the bar for developers, **check boxes** and add new gaps you found.
3. Keep claims in `README.md` and `AGENTS.md` aligned with reality—this checklist is the honest backlog.
