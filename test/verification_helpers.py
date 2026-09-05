from datetime import datetime, timezone

from engine.schemas import PARequest


def attest(evaluation, keys=None):
    """Synthetic test attestation only; production callers must actually review."""
    selected = {result.key for result in evaluation.results} if keys is None else set(keys)
    payload = evaluation.request.model_dump(mode="json")
    payload["fact_verifications"] = {
        result.key: {
            "state": "HUMAN_VERIFIED",
            "reviewer": "Synthetic test reviewer",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": result.verification_fingerprint,
        }
        for result in evaluation.results
        if result.key in selected
    }
    return PARequest.model_validate(payload)
