from __future__ import annotations
from typing import Any, Dict, List


def draft_letter_deterministic(
    payer: str,
    procedure_code: str,
    procedure_name: str,
    dx_codes: List[str],
    facts: Dict[str, Any],
    results: List[Dict[str, Any]],
) -> str:
    bullets = []
    for r in results:
        if r["status"] == "met":
            bullets.append(f"- {r['label']}: documented.")
        elif r["status"] == "weak":
            bullets.append(f"- {r['label']}: partially documented; may require clarification.")
        else:
            bullets.append(f"- {r['label']}: missing; add explicit documentation.")

    return (
        f"RE: Prior Authorization Request — {procedure_name} ({procedure_code})\n"
        f"Payer: {payer}\n"
        f"Diagnosis codes: {', '.join(dx_codes) if dx_codes else 'Not provided'}\n\n"
        "Summary of documentation (MVP demo):\n"
        + "\n".join(bullets)
        + "\n\n"
        "Request:\n"
        "Please review this request based on the attached clinical documentation and payer criteria.\n\n"
        "Disclaimer: This draft is generated for demonstration purposes only and is not medical or billing advice.\n"
    )

