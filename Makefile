.PHONY: venv install test lint eval harvest-cycles harvest-hydrogen graph-cycle analyze-cycle

PYTHON := .venv/bin/python

venv:
	python3 -m venv .venv

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

eval:
	$(PYTHON) -m trace_topology.cli eval --annotations data/samples/golden --samples data/samples --out eval.json

harvest-cycles:
	$(PYTHON) data/harvest.py --source ollama --provocation cycles --models llama3.1:8b,deepseek-r1:8b --repeats 1

harvest-hydrogen:
	$(PYTHON) data/harvest.py --source ollama --provocation hydrogen --models llama3.1:8b,deepseek-r1:8b --repeats 1

graph-cycle:
	$(PYTHON) -m trace_topology.cli graph data/samples/deepseek-r1-8b_circular_closed_loop_20260402.txt --out graph.closed-loop.json

analyze-cycle:
	$(PYTHON) -m trace_topology.cli analyze data/samples/deepseek-r1-8b_circular_closed_loop_20260402.txt --out analysis.closed-loop.json
