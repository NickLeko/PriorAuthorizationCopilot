"""Hand-authored synthetic proposals for structural tests, never model outputs."""

from engine.corrections import note_hash
from engine.fact_contracts import FACT_CONTRACTS
from experiments.dual_extraction.proposals import proposal_from_legacy


def synthetic_response(note, values=None, states=None, evidence=None):
    values, states, evidence = values or {}, states or {}, evidence or {}
    return {
        "recording": {
            "source": "recorded-llm:synthetic",
            "model_id": "synthetic-no-model",
            "prompt_version": "synthetic-schema-v1",
            "response_id": "synthetic-test-recording",
            "origin": "hand_authored_synthetic",
        },
        "note_sha256": note_hash(note),
        "facts": {
            key: {
                "state": states.get(key, "CAPTURED" if key in values else "MISSING"),
                "value": values.get(key),
                "evidence": evidence.get(key, [{"start": 0, "end": len(note), "text": note}] if key in values else []),
            }
            for key in FACT_CONTRACTS
        },
        "evidence_counts": {},
    }


def synthetic_regex(note, response):
    from engine.schemas import REVIEW_REQUIRED_FACT

    facts = {key: REVIEW_REQUIRED_FACT if item["state"] == "NEEDS_REVIEW" else item["value"] for key, item in response["facts"].items()}
    evidence = {key: item["evidence"] for key, item in response["facts"].items() if item["evidence"]}
    return proposal_from_legacy(note, (facts, evidence), source="synthetic-regex-proposal")
