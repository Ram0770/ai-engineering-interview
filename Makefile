.PHONY: help test test-p1 test-p2 lint lint-p1 lint-p2 run-p1 run-p2 demo-p1 demo-p2 eval eval-p1 eval-p2 seed-p1

PYTHON ?= python

help:
	@echo "Available commands:"
	@echo "  make test      : Run pytest test suites for both Problem 1 and Problem 2"
	@echo "  make lint      : Run ruff and mypy type checks on both projects"
	@echo "  make run-p1    : Start Problem 1 FastAPI server"
	@echo "  make run-p2    : Start Problem 2 Typer CLI interactive chat"
	@echo "  make demo-p1   : Run Problem 1 end-to-end interactive terminal demo"
	@echo "  make demo-p2   : Run Problem 2 single-query evaluation demo"
	@echo "  make eval      : Run 25-case routing eval (P1) and 22-case benchmark (P2)"
	@echo "  make seed-p1   : Run Swiggy/PhonePe/HDFC canonical scenario seed script"

test: test-p1 test-p2

test-p1:
	cd problem1-agent-network && $(PYTHON) -m pytest -v --cov=src

test-p2:
	cd problem2-hardware-assistant && $(PYTHON) -m pytest -v --cov=src

lint: lint-p1 lint-p2

lint-p1:
	cd problem1-agent-network && $(PYTHON) -m ruff check src tests eval scripts demo.py
	cd problem1-agent-network && $(PYTHON) -m mypy src

lint-p2:
	cd problem2-hardware-assistant && $(PYTHON) -m ruff check src tests eval scripts
	cd problem2-hardware-assistant && $(PYTHON) -m mypy src

run-p1:
	cd problem1-agent-network && $(PYTHON) -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

run-p2:
	cd problem2-hardware-assistant && $(PYTHON) -m src.cli chat

demo-p1:
	cd problem1-agent-network && $(PYTHON) demo.py

demo-p2:
	cd problem2-hardware-assistant && $(PYTHON) -m src.cli ask "Can I add more RAM, and how much?" --backend mock

eval: eval-p1 eval-p2

eval-p1:
	cd problem1-agent-network && $(PYTHON) eval/eval_routing.py --embedder sentence-transformers --threshold 0.68

eval-p2:
	cd problem2-hardware-assistant && $(PYTHON) eval/eval_suite.py --backend mock

seed-p1:
	cd problem1-agent-network && $(PYTHON) scripts/seed_demo.py
