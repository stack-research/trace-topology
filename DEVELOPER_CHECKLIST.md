# Developer checklist — making trace-topology broadly useful

This file tracks **what still needs doing** so the project is genuinely useful to developers debugging real LLM traces—not just a research prototype. Treat it as a living backlog: **update it** when you finish items, reprioritize, or discover new gaps.

Use `- [ ]` for open work and `- [x]` for done when you edit this file.

---

## Parser (step segmentation)

- [x] Reduce **over-segmentation** on terse, line-broken traces (e.g. some harvested Llama-style handshakes). — Heuristic: line-split only when structural list markers dominate or dense long-line prose blocks; see `data/samples/terse_linebreak_prose_0001.txt`.
- [x] Solid coverage for **mixed formats**: numbered lists, markdown headings, thinking blocks, code-heavy traces.
- [x] Document parser behavior and failure modes in `README.md` or a short `docs/` note. — `README.md` now explains segmentation rules, atomic regions, and known parser failure modes.

## Graph (support links and bond typing)

- [x] Continue improving **support-link construction** on real traces where steps are right but edges were thin. — Cycle calibration now adds reciprocal restatement links on repo-local cycle traces and regresses them in `tests/test_analysis.py` / `tests/test_eval.py`.
- [x] Calibrate **bond type** heuristics against more hand-annotated gold (not only synthetic). — Real handshake traces now regress cleanly in `tests/test_analysis.py` and `tests/test_eval.py`.
- [x] Clear rules for when **optional backends** (`--backend ollama|anthropic|openai`) help vs add noise; document defaults. — `README.md` now recommends `--backend none` for CI/eval, positions Ollama as local exploratory judging, and Anthropic / OpenAI as explicit external judging.

## Analysis (detectors)

- [x] Keep **contradiction / entropy** precise on long prose without tanking recall on gold. — Precision-tuned contradiction detection, verification-tail entropy suppression, and handshake regressions are covered by `tests/test_detectors.py`.
- [x] **Cycle detection**: validate on diverse real cyclic traces, not only closed-loop prompts. — Gold now includes `synthetic_cycle_trust`, `deepseek-r1-8b_circular_closed_loop`, and two real `circular_trust` traces with cycle-specific eval assertions.
- [x] Consider **severity tuning** or ranking so the CLI surfaces the most actionable findings first. — Findings are now ranked deterministically by severity, score, type priority, and step order; `tt analyze` also supports severity-aware and score-aware CI gates.

## Rendering and CLI

- [x] **ASCII layout** for large traces: compression, grouping, or phase summaries so output stays readable in a normal terminal. — `render.py` now switches to adaptive compact mode at 15+ steps with phase summaries, aggregated phase links, and finding-local hotspots in `tt analyze`.
- [x] **Stable JSON schemas** across versions; document breaking changes in `README.md`. — Top-level artifacts now carry `artifact_type` and `schema_version = 1`, with the compatibility rule documented in `docs/ARTIFACT_CONTRACT.md`.
- [x] **Exit codes** (e.g. non-zero when structural failures exceed a threshold) for CI integration. — `tt analyze --fail-on-findings`; `tt eval --min-avg-bond-recall` (and related floors).
- [x] Keep **CLI/docs/examples aligned**: when flags or commands change, update `README.md` and `AGENTS.md` in the same pass; keep smoke tests for documented CLI surfaces.

## Developer experience

- [x] **CI** (lint + tests on push/PR) if the repo is public or multi-contributor. — `.github/workflows/ci.yml` (uv, ruff, pytest).
- [x] **Pre-commit** or documented `make`/`uv` one-liners for format + test before commit. — README **Development** section + existing Makefile.
- [x] **Example sessions** in `README.md`: harvest → analyze → eval on a sample file. — README now includes sample-file and optional harvest walkthroughs with expected artifact outputs, plus a separate developer-first runnable session in `docs/FIRST_DEBUG_SESSION.md`.
- [x] Preserve the **zero-network core path**: parse/graph/analyze should still work when optional backend dependencies are not installed. — backend SDKs stay out of the base install, and missing backend deps now fail with explicit install hints for `ollama`, `anthropic`, and `openai`.

## Data and evaluation

- [ ] Grow **golden annotations** for real traces (hand-reviewed or assisted + corrected). — Current gold set includes 19 annotations, now covering the remaining real Llama closed-loop trace (`llama3.1-8b_circular_closed_loop`) in addition to the probability controls and long-form circular cases; future growth is now incremental rather than release-blocking.
- [x] **Regression gates**: `tt eval` summary thresholds or trend notes in this checklist. — Current calibrated floor set: `avg_bond_precision >= 0.80`, `avg_bond_recall >= 0.88`, `avg_finding_precision >= 0.80`, `avg_finding_recall >= 0.75`; non-zero exit when below floor.
- [x] **UQM / external corpus** import path documented and tested when data is available. — `data/harvest.py --source uqm` now imports a curated crack slice deterministically, `make harvest-uqm` wraps it, and fixture-backed tests cover filtering, naming, and provenance metadata.

## Ecosystem (later, optional)

- [ ] Parser **configurable granularity** (sentence vs paragraph vs heuristic) for power users.
- [ ] **Packaging** polish: `pip install`/Homebrew story if adoption matters.
- [ ] Editor or **LSP** integration (jump to step from finding)—only if terminal-first scope expands.
- [ ] **Stable library API** (`import trace_topology`) for embedding in other tools—document supported surfaces.

---

## How to use this file

1. Before a focused sprint, pick a section and move the top items into issues or commits.
2. After a merge that advances the bar for developers, **check boxes** and add new gaps you found.
3. Keep claims in `README.md` and `AGENTS.md` aligned with reality—this checklist is the honest backlog.
