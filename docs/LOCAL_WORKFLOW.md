# Local Workflow

Current repo status:
- deterministic extraction, evaluation, and letter drafting
- no LLM implementation

## Canonical Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Test

```bash
pytest -q
```

`pytest -q` is the CI path. It covers deterministic extraction, evaluation semantics, drafting constraints, rule loading, policy-monitor helpers, and a regression check over the bundled synthetic eval cases.

The Streamlit UI separately surfaces the same bundled synthetic eval cases as a local demo gate.
