PYTHON ?= python3
VENV_PYTHON ?= .venv/bin/python
CASE ?= MRI-01-complete
RUN_PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(PYTHON))

.PHONY: install run api test lint format artifacts cli-status reviewer-demo verify smoke-ui evaluate-case acceptance goldens

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

reviewer-demo:
	$(RUN_PYTHON) cli.py status
	$(RUN_PYTHON) cli.py list-demo-cases
	$(RUN_PYTHON) cli.py evaluate --demo-case MRI-01-complete
	$(RUN_PYTHON) cli.py evaluate --demo-case MRI-08-edge-below-threshold
	$(RUN_PYTHON) cli.py evaluate --demo-case CPAP-02-borderline
	$(RUN_PYTHON) cli.py export-report --demo-case CPAP-02-borderline --output /tmp/pa-copilot-reviewer-demo.json --with-letter --letter-type missing_info_request

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
	$(RUN_PYTHON) -m ruff format --check .

format:
	$(RUN_PYTHON) -m ruff format .

artifacts:
	$(RUN_PYTHON) -m scripts.generate_artifacts

goldens:
	$(RUN_PYTHON) -m scripts.generate_golden_outputs

verify: lint test artifacts goldens
