"""Byte-exact oracle comparison; frozen sources are from main b6b5c82.

Only the frozen extractor's relative schemas import is relocated. Its code and
the frozen citation code remain unchanged. Generated notes are deliberately
small so the vulnerable oracle stays fast.
"""

import json
import random
import re
from pathlib import Path

import pytest
from frozen_v212.citation_context import citation_context as old_context
from frozen_v212.extract import extract_facts as old_extract

from engine.citation_context import citation_context
from engine.evaluate import compute_overall_status, evaluate_requirements
from engine.extract import extract_facts
from engine.note_context import indexed_note
from engine.rules_loader import load_rules


def cases():
    corpus = json.loads(Path("inputs/synthetic_cases.json").read_text())
    independent = json.loads(Path("test/fixtures/v210_independent.json").read_text())
    notes = [(f"corpus-{c['id']}", c["note_text"], c["procedure_code"]) for c in corpus]
    notes += [(f"independent-{c['id']}", c["note"], c["procedure"]) for c in independent]
    vocabulary = [part.strip() for c in corpus for part in re.split(r"[.!?;\n]+", c["note_text"]) if part.strip()]
    vocabulary += [
        "AHI unknown",
        "AHI 12, RDI not stated",
        "AHI 12; RDI missing",
        "PT for 6 weeks, whereas NSAIDs for 8 weeks",
        "mother reports OSA",
        "patient denies weakness",
        "history of pain",
        "PT ordered",
        "Sleep study 2024-05-18",
        "İ OSA",
        "strength 4.5/5 in L5 distribution",
    ]
    rng = random.Random(213)
    for i in range(600):
        pieces = rng.sample(vocabulary, rng.randint(1, 4))
        separator = rng.choice([". ", "; ", "? ", "! ", "\n", ", whereas ", " but ", " \t "])
        note = separator.join(pieces)
        note = note.replace(" ", rng.choice([" ", "  ", "\t", " \t "]))
        notes.append((f"generated-{i:03}", note, rng.choice(["MRI_LUMBAR", "MRI_KNEE", "CPAP_DEVICE"])))
    return notes


CASES = cases()
RULES = load_rules("rules/payer_rules.yaml")


def projection(extractor, context, note, procedure):
    facts, evidence = extractor(note)
    requirements = RULES["payers"]["Aetna"]["procedures"][procedure]["required"]
    results, _ = evaluate_requirements(requirements, facts, evidence_map=evidence)
    with indexed_note(note):
        contexts = {key: [context(note, span["start"], span["end"]) for span in spans] for key, spans in evidence.items()}
    payload = {
        "facts": facts,
        "states": {
            key: "NEEDS_REVIEW" if value == "__REVIEW_REQUIRED__" else "MISSING" if value is None else "CAPTURED"
            for key, value in facts.items()
        },
        "spans": evidence,
        "contexts": contexts,
        "requirements": [result.model_dump(mode="json") for result in results],
        "overall": compute_overall_status(results),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize("name,note,procedure", CASES, ids=[c[0] for c in CASES])
def test_byte_exact_v212_equivalence(name, note, procedure):
    assert projection(extract_facts, citation_context, note, procedure) == projection(old_extract, old_context, note, procedure), name
