from __future__ import annotations

from typing import Any, Dict, List


def draft_letter_deterministic(
    payer: str,
    procedure_code: str,
    procedure_name: str,
    dx_codes: List[str],
    facts: Dict[str, Any],
    results: List[Dict[str, Any]],
    overall_status: str = "UNKNOWN",
) -> str:
    """
    Deterministic draft for MVP.

    IMPORTANT:
    - Uses tri-state statuses: MET / NOT_MET / NOT_DOCUMENTED
    - If overall_status == CANNOT_DETERMINE, this becomes a "documentation gap memo"
      (safe, non-deceptive, prevents false confidence).
    """

    met_items = [r for r in results if r.get("status") == "MET"]
    not_met_items = [r for r in results if r.get("status") == "NOT_MET"]
    not_doc_items = [r for r in results if r.get("status") == "NOT_DOCUMENTED"]

    dx_str = ", ".join(dx_codes) if dx_codes else "Not provided"

    header = (
        f"RE: Prior Authorization Request — {procedure_name} ({procedure_code})\n"
        f"Payer: {payer}\n"
        f"Diagnosis codes: {dx_str}\n\n"
    )

    disclaimer = (
        "\nDisclaimer: This draft is for administrative preparation only and does not constitute medical or billing advice. "
        "All outputs require human review prior to submission.\n"
    )

    # --------
    # Mode A: Documentation gap memo (CANNOT_DETERMINE)
    # --------
    if overall_status == "CANNOT_DETERMINE":
        lines = [
            header,
            "Documentation Gap Summary (Action Required):\n",
            "The following required policy elements were not found in the provided note. "
            "Please add explicit documentation before submission.\n",
        ]

        if not_doc_items:
            lines.append("Missing documentation:\n")
            for r in not_doc_items:
                lines.append(f"- {r['label']}: {r['reason']}")
        else:
            lines.append("Missing documentation: none detected (unexpected for CANNOT_DETERMINE).\n")

        # Include what IS documented (helps user see progress)
        if met_items:
            lines.append("\nItems already documented:\n")
            for r in met_items:
                lines.append(f"- {r['label']}: documented and meets requirement.")

        lines.append(
            "\nRequest:\n"
            "Please review once the missing documentation is added.\n"
        )
        lines.append(disclaimer)
        return "".join(lines)

    # --------
    # Mode B/C: Standard draft (NOT_READY or READY or UNKNOWN)
    # --------
    bullets = []

    for r in results:
        status = r.get("status")
        if status == "MET":
            bullets.append(f"- {r['label']}: documented and meets requirement.")
        elif status == "NOT_MET":
            bullets.append(f"- {r['label']}: documented but does not meet requirement threshold.")
        elif status == "NOT_DOCUMENTED":
            bullets.append(f"- {r['label']}: not documented; add explicit clinical detail.")
        else:
            bullets.append(f"- {r.get('label', 'Unknown requirement')}: status unclear.")

    # If NOT_READY, avoid sounding like a confident approval request
    if overall_status == "NOT_READY":
        request_line = (
            "Request:\n"
            "This draft summarizes current documentation relative to policy criteria. "
            "One or more requirements appear documented but not met; human review is required before submission.\n"
        )
    else:
        request_line = (
            "Request:\n"
            "Please review this request based on the attached clinical documentation and payer criteria.\n"
        )

    return (
        header
        + "Documentation Status Summary:\n"
        + "\n".join(bullets)
        + "\n\n"
        + request_line
        + disclaimer
    )
