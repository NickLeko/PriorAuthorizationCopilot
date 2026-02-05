import streamlit as st

from engine.rules_loader import load_rules
from engine.extract import extract_facts
from engine.evaluate import (
    evaluate_requirements,
    compute_readiness_score,
    compute_overall_status,
)
from llm.draft_letter import draft_letter_deterministic


# ----------------------------
# Page config + CSS
# ----------------------------
st.set_page_config(page_title="PA Readiness Copilot", layout="wide")

st.markdown(
    """
    <style>
      html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        height: 100% !important;
        overflow: auto !important;
        -webkit-overflow-scrolling: touch !important;
      }
      header[data-testid="stHeader"] { position: relative !important; }
      section[data-testid="stSidebar"], div[data-testid="stVerticalBlock"] { overflow: visible !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("PA Readiness Copilot (Flagship)")
st.caption("Administrative decision support only — not medical or billing advice.")


# ----------------------------
# Session state initialization
# ----------------------------
if "last_eval" not in st.session_state:
    st.session_state.last_eval = None  # stores last evaluation outputs
if "test_rows" not in st.session_state:
    st.session_state.test_rows = None  # stores last test suite output


# ----------------------------
# Load rules
# ----------------------------
RULES_PATH = "rules/payer_rules.yaml"
rules = load_rules(RULES_PATH)
payers = sorted(rules["payers"].keys())


# ----------------------------
# Intake form
# ----------------------------
st.markdown("### Intake")

with st.form("pa_form", clear_on_submit=False):
    c1, c2, c3 = st.columns(3)

    with c1:
        payer = st.selectbox("Payer", payers)

    with c2:
        procedures = rules["payers"][payer]["procedures"]
        proc_code = st.selectbox("Procedure", list(procedures.keys()))

    with c3:
        dx_raw = st.text_input("Dx codes (comma-separated)", placeholder="e.g., M54.5, M51.26")

    specialty = st.text_input("Ordering specialty (optional)", placeholder="e.g., Orthopedics")
    site = st.selectbox("Site of care", ["outpatient", "inpatient", "ASC", "office"])

    note_text = st.text_area(
        "Clinical note (mock/synthetic)",
        height=220,
        placeholder="Paste a synthetic note here...",
    )

    submitted = st.form_submit_button("Evaluate PA readiness")


# ----------------------------
# Evaluate action (persist results)
# ----------------------------
if submitted:
    dx_codes = [x.strip() for x in (dx_raw or "").split(",") if x.strip()]
    proc_obj = rules["payers"][payer]["procedures"][proc_code]
    proc_name = proc_obj.get("display_name", proc_code)
    requirements = proc_obj.get("required", [])

    facts = extract_facts(note_text)
    results, reasons = evaluate_requirements(requirements, facts)

    overall = compute_overall_status(results)
    score_info = compute_readiness_score(results)

    rows = [
        {
            "key": r.key,
            "label": r.label,
            "status": r.status,  # expects: MET / NOT_MET / NOT_DOCUMENTED
            "reason": r.reason,
            "evidence_hint": r.evidence or "",
        }
        for r in results
    ]

    letter = draft_letter_deterministic(
        payer=payer,
        procedure_code=proc_code,
        procedure_name=proc_name,
        dx_codes=dx_codes,
        facts=facts,
        results=rows,
    )

    audit = {
        "payer": payer,
        "procedure_code": proc_code,
        "procedure_name": proc_name,
        "site_of_care": site,
        "specialty": specialty,
        "rules_version": rules.get("version"),
        "facts_extracted": facts,
        "requirements_checked": [r["key"] for r in rows],
        "overall_status": overall["overall_status"],
        "submission_readiness": bool(overall["submission_readiness"]),
    }

    st.session_state.last_eval = {
        "payer": payer,
        "proc_code": proc_code,
        "proc_name": proc_name,
        "dx_codes": dx_codes,
        "facts": facts,
        "results": results,
        "rows": rows,
        "reasons": reasons,
        "overall": overall,
        "score_info": score_info,
        "letter": letter,
        "audit": audit,
    }


# ----------------------------
# Outputs (render if we have last_eval)
# ----------------------------
st.markdown("### Outputs")

if st.session_state.last_eval is None:
    st.info("Run an evaluation to see case outputs. Test suite can be run anytime below.")
else:
    ev = st.session_state.last_eval
    overall = ev["overall"]
    score_info = ev["score_info"]

    status = overall["overall_status"]
    submission_readiness = bool(overall["submission_readiness"])

    # Bias-resistant banner
    if status == "CANNOT_DETERMINE":
        st.warning(
            "Approval readiness **cannot be determined** — one or more required criteria are **not documented** in the note. "
            "Add explicit documentation for the blocking items below."
        )
    elif status == "NOT_READY":
        st.error(
            "Not ready to submit — one or more required criteria are **documented but not met**. "
            "Review the failing items below."
        )
    elif status == "READY":
        st.success(
            "Administratively ready **per current rules** — all required criteria appear documented and met. "
            "Human review still required."
        )
    else:
        st.info("Status unavailable (unexpected overall_status).")

    o1, o2 = st.columns([1, 2])

    with o1:
        st.metric("PA Readiness Score", f"{score_info['readiness_score']}/100")
        st.write(
            {
                "met": score_info["met_count"],
                "not_documented": score_info["not_documented_count"],
                "not_met": score_info["not_met_count"],
                "total": score_info["total"],
            }
        )
        st.write({"overall_status": status, "submission_readiness": submission_readiness})

    with o2:
        st.subheader("Blocking Items (Most Important)")
        results = ev["results"]
        not_documented_items = [r for r in results if r.status == "NOT_DOCUMENTED"]
        not_met_items = [r for r in results if r.status == "NOT_MET"]

        if not not_documented_items and not not_met_items:
            st.success("No blocking items detected by current rules.")
        else:
            if not_documented_items:
                st.markdown("**Missing documentation (cannot determine readiness):**")
                for r in not_documented_items:
                    st.write(f"- {r.label}: {r.reason}")

            if not_met_items:
                st.markdown("**Documented but not met (not ready):**")
                for r in not_met_items:
                    st.write(f"- {r.label}: {r.reason}")

    st.subheader("Rule-based Requirement Results")
    st.dataframe(ev["rows"], use_container_width=True)

    st.subheader("Draft Justification Letter (deterministic MVP)")
    st.text_area("Letter draft", value=ev["letter"], height=220)

    st.subheader("Audit Trail")
    st.json(ev["audit"])


# ----------------------------
# Test suite (independent of eval)
# ----------------------------
st.markdown("### Test Suite (Synthetic Cases)")

c1, c2 = st.columns([1, 3])
with c1:
    run_tests = st.button("Run test suite", use_container_width=True)

if run_tests:
    from engine.test_suite import run_cases

    st.session_state.test_rows = run_cases("rules/payer_rules.yaml", "inputs/synthetic_cases.json")

if st.session_state.test_rows is None:
    st.caption("Click **Run test suite** to evaluate the rules engine on synthetic cases.")
else:
    st.dataframe(st.session_state.test_rows, use_container_width=True)
