PYTHON ?= python3.12
VENV_PYTHON ?= .venv/bin/python

.PHONY: install run test

install:
	$(PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt

run:
	$(VENV_PYTHON) -m streamlit run app.py

test:
	$(VENV_PYTHON) -m pytest -q
