PY := python3
VENV := .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTHON := $(BIN)/python

IN_DEFAULT := input/exhaust.jsonl
OUT_DEFAULT := output

DEPS_STAMP := $(VENV)/.deps-installed

$(DEPS_STAMP): requirements.txt
	@$(PY) -m venv $(VENV)
	@$(PIP) install -r requirements.txt
	@mkdir -p input output
	@touch input/.gitkeep output/.gitkeep
	@touch $(DEPS_STAMP)

.PHONY: deps run demo clean nuke

deps: $(DEPS_STAMP)
	@echo "OK: deps"

demo: deps
	@$(PYTHON) -m pitstop_scan.demo --out $(IN_DEFAULT)
	@$(PYTHON) -m pitstop_scan.cli --in $(IN_DEFAULT) --out $(OUT_DEFAULT)
	@test -f $(OUT_DEFAULT)/report.md && echo "OK: wrote $(OUT_DEFAULT)/report.md" || (echo "ERROR: missing report.md" && exit 1)

run: deps
	@$(PYTHON) -m pitstop_scan.cli --in $(IN_DEFAULT) --out $(OUT_DEFAULT)

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