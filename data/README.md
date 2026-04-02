# data/: Transcript Corpus

This directory holds the reasoning transcripts that trace-topology analyzes. The quality of the tool lives or dies on this corpus.

## What makes a transcript useful

Not length — structural variety. A useful transcript contains the specific features the analyzer needs to detect: self-corrections, circular reasoning, abandoned threads, contradictions, entropy divergence. Short transcripts with clear structural features beat long clean ones.

## Farming procedure

### Provocation categories

Each provocation is designed to trigger a different structural feature in the reasoning trace.

**For self-correction bonds (hydrogen):** Ask models to solve something where the obvious first approach is wrong. Classic: "There are 8 people in a room. Each shakes hands with every other person exactly once. How many handshakes?" Then add a wrinkle: "3 of them are wearing gloves and won't shake bare hands." The model often commits to the clean formula first, then catches itself. That backtrack is a hydrogen bond.

**For circular reasoning (cycles):** Ask for justifications of self-referential claims. "Why should I trust LLM output?" often produces loops where the model cites its own reliability as evidence of reliability. Philosophical questions work too — "Is free will compatible with determinism?" tends to go circular in longer traces.

**For abandoned threads (dangling nodes):** Give multi-part problems where one part is much harder. "Solve these three problems: [easy], [hard], [easy]." The hard one gets a partial attempt that dangles while the model pivots to finish the others and never returns.

**For contradiction pairs:** Give problems with subtly conflicting constraints. "Design a system that's both fully transparent and protects user privacy." The model asserts both goals, then makes claims that serve one while undermining the other — often without noticing.

**For entropy divergence:** Long open-ended reasoning. "What are the implications of quantum computing for cryptography, and what should organizations do about it?" Extended thinking on vague questions loses focus. The reasoning gets broader and shallower, which is measurable.

**For bond imbalance:** Ask something the model is uncertain about. "Is P=NP?" or domain-specific questions near the edge of training data. Models over-index on self-reflection ("I should note that...", "It's worth considering...") without advancing the argument. All hydrogen, no covalent.

### Collection procedure

1. Run each provocation against 3+ models: Claude with extended thinking, DeepSeek-R1 via Ollama, Llama 3.1 (8b and/or 70b). Same prompt, different architectures — the structural differences between models are themselves interesting data.

2. Extract the raw thinking/reasoning trace. For Claude, the thinking block. For DeepSeek-R1, the full output before the final answer. Strip the final answer — just the trace.

3. Hand-annotate 5-10 transcripts as ground truth. Mark where bonds are, what type, where failures occur. These become golden test fixtures. See `annotation_schema.json` for the format.

4. Pull crack responses from `../the-unaskable-question-machine/data/`. The UQM already has 13 classified crack responses from its runs — structural breakdowns under impossible questions. These are ideal pathological test cases. Use `harvest.py --source uqm` to extract them.

5. Store everything in `data/samples/` with naming convention: `{model}_{provocation}_{id}.txt` for the raw trace, `{model}_{provocation}_{id}.json` for the annotation.

### Automation

`harvest.py` automates steps 1-2 and step 4:

- `python harvest.py --source ollama --provocation all` — run all provocations against local Ollama model
- `python harvest.py --source uqm` — extract crack responses from UQM data files
- `python harvest.py --source ollama --provocation cycles --model deepseek-r1:8b` — targeted run
- `python harvest.py --source anthropic --provocation contradiction --model claude-3-5-sonnet-latest` — Anthropic run
- `python harvest.py --source ollama --provocation all --models llama3.1:8b,deepseek-r1:8b --repeats 2` — matrix run

Step 3 (annotation) is manual. That's the bottleneck. But even 10 well-annotated transcripts is enough to validate the parser and analyzer against real structure.

### Assisted annotation flow

Manual annotation is still required for high-quality gold data, but authoring from scratch is too slow.
Use `assist_annotate.py` to draft annotations, then review and correct:

- `python assist_annotate.py --transcript "*.txt"` — draft all
- `python assist_annotate.py --transcript "synthetic_*"` — draft subset

Drafts are written under `data/samples/golden/` and must be corrected before being treated as golden fixtures.

## Directory layout

```
data/
  README.md               — this file
  harvest.py              — transcript collection automation
  annotation_schema.json  — schema for ground truth annotations
  samples/                — collected transcripts and annotations
```
