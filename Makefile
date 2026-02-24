SHELL := /bin/bash

VENV := .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTHON := $(BIN)/python

IN_DEFAULT := input/exhaust.jsonl
OUT_DEFAULT := output
SCHEMA_DEFAULT := schemas/decision_event.v1.schema.json

# Allow overrides: make scan IN=... OUT=... SCHEMA=...
IN ?= $(IN_DEFAULT)
OUT ?= $(OUT_DEFAULT)
SCHEMA ?= $(SCHEMA_DEFAULT)

DEPS_STAMP := $(VENV)/.deps-installed

.DEFAULT_GOAL := help

.PHONY: help deps scan run demo validate clean nuke

help:
	@echo ""
	@echo "pitstop-scan targets:"
	@echo "  make deps                 Create venv + install deps"
	@echo "  make validate              Validate IN against SCHEMA"
	@echo "  make scan                  Run scan (validates IN first)"
	@echo "  make demo                  Write demo JSONL -> IN, then scan"
	@echo "  make clean                 Remove venv + clear output/"
	@echo "  make nuke                  Remove venv + clear input/ + output/"
	@echo ""
	@echo "Overrides:"
	@echo "  make scan IN=... OUT=... SCHEMA=..."
	@echo ""

$(DEPS_STAMP): requirements.txt
	@python3 -m venv $(VENV)
	@$(PYTHON) -m pip install -U pip >/dev/null
	@$(PYTHON) -m pip install -r requirements.txt >/dev/null
	@mkdir -p input output
	@touch input/.gitkeep output/.gitkeep
	@touch $(DEPS_STAMP)

deps: $(DEPS_STAMP)
	@echo "OK: deps"

validate: deps
	@test -f "$(SCHEMA)" || { echo "ERROR: missing schema: $(SCHEMA)"; exit 2; }
	@test -s "$(IN)" || { echo "ERROR: missing/empty input: $(IN)"; echo "Fix: make demo OR provide IN=path/to/exhaust.jsonl"; exit 2; }
	@$(PYTHON) -c 'from pitstop_scan.schema_validate import validate_jsonl_against_schema as v; n=v("$(IN)","$(SCHEMA)"); print(f"OK: validated {n} events against $(SCHEMA)")'

# scan is the public-facing verb; keep run as an alias for muscle memory
scan: validate
	@$(PYTHON) -m pitstop_scan.cli --in "$(IN)" --out "$(OUT)"
	@test -f "$(OUT)/report.md" || { echo "ERROR: missing $(OUT)/report.md"; exit 1; }
	@echo "OK: wrote $(OUT)/report.md"

run: scan

demo: deps
	@$(PYTHON) -m pitstop_scan.demo --out "$(IN)"
	@$(MAKE) -s scan IN="$(IN)" OUT="$(OUT)" SCHEMA="$(SCHEMA)"

clean:
	@rm -rf $(VENV)
	@rm -rf output/*
	@touch output/.gitkeep
	@echo "OK: cleaned"

nuke:
	@rm -rf $(VENV)
	@rm -f input/exhaust.jsonl
	@rm -rf output/*
	@touch input/.gitkeep output/.gitkeep
	@echo "OK: nuked"

.PHONY: selftest
selftest: nuke demo
	@echo "OK: selftest"