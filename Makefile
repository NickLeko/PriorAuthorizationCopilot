PYTHON ?= python3
VENV_PYTHON ?= .venv/bin/python
STREAMLIT ?= .venv/bin/streamlit
PIP ?= .venv/bin/pip
PYTEST ?= .venv/bin/pytest

.PHONY: install run test

install:
	$(PYTHON) -m venv .venv
	$(PIP) install -r requirements.txt

run:
	$(STREAMLIT) run app.py

test:
	$(PYTEST) -q
