# References

Papers, tools, and prior art surveyed during the design of trace-topology.

## Core Foundation

- **The Molecular Structure of Thought: Mapping the Topology of Long Chain-of-Thought Reasoning** (ByteDance, Jan 2026). arXiv 2601.06002. Introduces covalent/hydrogen/van der Waals bond taxonomy for CoT reasoning. Our primary theoretical framework. https://arxiv.org/abs/2601.06002

## Reasoning Topology Research

- **Topologies of Reasoning: Demystifying Chains, Trees, and Graphs of Thoughts** (ETH Zürich, 2024). arXiv 2401.14295. Categorizes CoT, ToT, GoT as structural patterns. Taxonomy, not tooling. https://arxiv.org/abs/2401.14295
- **Verifying Chain-of-Thought Reasoning via Its Computational Graph** (Oct 2025). arXiv 2510.09312. Attribution graphs for step correctness. Requires model internals; we work on text transcripts alone. https://arxiv.org/abs/2510.09312

## Visualization Tools (Browser-Based)

- **Landscape of Thoughts**. First visualization tool for reasoning paths across multiple-choice datasets. t-SNE on feature vectors. https://landscape-of-thoughts.github.io/
- **ReasonGraph** (Mar 2025). arXiv 2503.03979. Flowchart illustration of reasoning methods. https://arxiv.org/abs/2503.03979
- **Hippo** (UIST 2025). Interactive tree-based reasoning steering. https://homes.cs.washington.edu/~ypang2/papers/uist25-interactive-reasoning.pdf

## Stack Research (Internal)

- **The Unaskable Question Machine**. Probes structural impossibilities in LLMs. Its "crack" responses (structural breakdown under impossible questions) are ideal pathological test inputs. https://stackresearch.org/research/the-unaskable-question-machine/
- **Intelligence Beyond Autocomplete**. Five post-LLM directions including "topology-native graph operators" as an underbuilt substrate. https://stackresearch.org/research/intelligence-beyond-autocomplete/
- **AI That Refuses to Predict**. The case for systems that output structure (causal graphs, state machines) instead of prose. Core design influence. https://stackresearch.org/research/ai-that-refuses-to-predict/
- **Genetic Prompt Programming**. Evolutionary prompt optimization. trace-topology could serve as a fitness signal: prompts that produce better-structured reasoning score higher. https://stackresearch.org/research/genetic-prompt-programming/

## Prompting Frameworks (Context, Not Dependencies)

- **Graph-of-Thought** (2023). arXiv 2305.16582. Models thought as a graph during inference. We analyze the graph after the fact. https://arxiv.org/abs/2305.16582
- **Graph Chain-of-Thought** (2024). arXiv 2404.07103. Augments LLMs by reasoning on explicit graphs. Different goal (steering vs debugging). https://arxiv.org/abs/2404.07103
