PYTHON ?= python3
VENV_PYTHON ?= .venv/bin/python
CASE ?= MRI-01-complete
RUN_PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(PYTHON))

.PHONY: install run api test lint format artifacts cli-status verify smoke-ui evaluate-case acceptance goldens

install:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt

run:
	$(RUN_PYTHON) -m streamlit run app.py

api:
	$(RUN_PYTHON) -m uvicorn api:app --reload

cli-status:
	$(RUN_PYTHON) cli.py status

evaluate-case:
	$(RUN_PYTHON) cli.py evaluate --demo-case $(CASE)

test:
	$(RUN_PYTHON) -m pytest -q

acceptance:
	$(RUN_PYTHON) -m pytest -q test/test_acceptance_snapshots.py

smoke-ui:
	$(RUN_PYTHON) -m pytest -q test/test_streamlit_app.py

lint:
	$(RUN_PYTHON) -m ruff check .

format:
	$(RUN_PYTHON) -m ruff format .

artifacts:
	$(RUN_PYTHON) -m scripts.generate_artifacts

goldens:
	$(RUN_PYTHON) -m scripts.generate_golden_outputs

verify: lint test artifacts goldens
