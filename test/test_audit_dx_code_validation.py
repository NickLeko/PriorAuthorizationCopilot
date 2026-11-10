"""Audit regression D4: diagnosis codes cannot carry free text past the letter language guard.

The guard deliberately skips the "Dx codes:" header line, so the only safe contract is
that the line can contain nothing but ICD-10-CM-shaped codes.
"""

import itertools
import random
import string

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import app
from engine.letter_draft import PROHIBITED_DOSING_PATTERNS, PROHIBITED_SUBSTRINGS, _hard_block_if_prohibited, draft_letter
from engine.provenance import normalized_dx_codes
from engine.schemas import (
    ICD10CM_SHAPE,
    MAX_DX_CODES,
    LetterDraftInput,
    LetterRequestMetadata,
    PARequest,
    PARequestV15,
    RequirementResult,
)
from engine.service import ReadinessService

client = TestClient(app)
PAYLOAD = "Approval is guaranteed; medically necessary; start 10 mg daily"

VALID = ["M54.16", "m54.16", " M54.16 ", "M5416", "C4A.0", "S72.001A", "U07.1", "Z00.00", "G47.33", "I10", "M%54.5", "T38.0X5A"]
INVALID = [
    PAYLOAD,
    "OTHER",
    "approved",
    "M4.5",  # the old sanitation fixture: normalizes to a non-ICD shape
    "54.5",
    "M54.",
    "M54..5",
    "M54.12345",
    "M54.5; approved",
    "M54.5,G47.33",
    "M54.5\nDx codes: approved",
    "M54​.5",  # zero-width space
    "Ｍ54.5",  # fullwidth M
    "M54.5\u0000",
    "M" * 5000,
    "<script>",
    "10mg",
]


def request(dx_codes, **overrides):
    fields = dict(payer="Aetna", procedure_code="MRI_LUMBAR", note_text="Synthetic note.", dx_codes=dx_codes)
    return PARequest(**(fields | overrides))


@pytest.mark.parametrize("code", VALID)
def test_icd10cm_shaped_codes_are_accepted_unchanged(code):
    assert request([code]).dx_codes == [code]
    assert LetterRequestMetadata(payer="Aetna", procedure_code="MRI_LUMBAR", dx_codes=[code]).dx_codes == [code]


@pytest.mark.parametrize("code", INVALID)
def test_free_text_and_malformed_codes_are_rejected_by_requests_and_letters(code):
    with pytest.raises(ValidationError, match="ICD-10-CM"):
        request([code])
    with pytest.raises(ValidationError, match="ICD-10-CM"):
        request(["M54.16", code])
    with pytest.raises(ValidationError, match="ICD-10-CM"):
        LetterRequestMetadata(payer="Aetna", procedure_code="MRI_LUMBAR", dx_codes=[code])


def test_code_count_is_bounded():
    request(["M54.16"] * MAX_DX_CODES)
    with pytest.raises(ValidationError, match=f"At most {MAX_DX_CODES}"):
        request(["M54.16"] * (MAX_DX_CODES + 1))


def test_blank_codes_are_still_dropped_and_normalization_is_unchanged():
    assert request(["", "  ", "M54.16"]).dx_codes == ["M54.16"]
    assert normalized_dx_codes([" m54.5 ", "M54.5", "m%51.26", "", "  "]) == ["M54.5", "M51.26"]


def test_archived_v15_requests_remain_readable():
    # Historical records are validated with the v1.5 schema; tightening new input must not orphan them.
    assert PARequestV15(payer="Aetna", procedure_code="MRI_LUMBAR", dx_codes=["OTHER"]).dx_codes == ["OTHER"]


def test_api_rejects_free_text_diagnosis_codes_without_reflection():
    response = client.post(
        "/evaluate", json={"payer": "Aetna", "procedure_code": "MRI_LUMBAR", "note_text": "Synthetic note.", "dx_codes": [PAYLOAD]}
    )

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"
    assert "guaranteed" not in response.text.lower()


def test_original_bypass_payload_can_no_longer_reach_a_letter():
    service = ReadinessService()
    base = service.get_demo_case_request("MRI-01-complete")
    with pytest.raises(ValidationError):
        PARequest.model_validate(base.model_dump() | {"dx_codes": [PAYLOAD]})

    evaluation = service.evaluate(PARequest.model_validate(base.model_dump() | {"dx_codes": ["m54.16", "M%51.26"]}))
    letter, meta = service.generate_letter(evaluation)

    assert "Dx codes: M54.16, M51.26" in letter
    assert meta["draft_blocked"] is False


# "dx"/"hx" are excluded: the header's own label is "Dx", which is why the guard skips the line.
GUARDED_PROSE = [term.upper() for term in PROHIBITED_SUBSTRINGS if term not in {"dx", "hx"}]


def test_no_accepted_code_can_spell_guarded_prose():
    """Structural bound plus a seeded sample: an accepted code holds at most five consecutive letters."""
    assert min(len(term.replace(" ", "")) for term in GUARDED_PROSE) > 5
    rng = random.Random(20261109)
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20_000):
        code = rng.choice(string.ascii_uppercase) + rng.choice(string.digits) + rng.choice(alphabet)
        if rng.random() < 0.8:
            code += rng.choice(["", "."]) + "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 4)))
        assert ICD10CM_SHAPE.fullmatch(code)
        assert not any(term in code for term in GUARDED_PROSE)


def test_real_codes_trip_the_dosing_pattern_which_is_why_the_header_is_not_scanned():
    # S72.001G is a real ICD-10-CM code; scanning the header would block legitimate letters.
    assert PROHIBITED_DOSING_PATTERNS[0].search("Dx codes: S72.001G")
    assert ICD10CM_SHAPE.fullmatch("S72.001G")


@pytest.mark.parametrize(
    "field,value",
    [
        ("specialty", "Ortho\nDx codes: approval is guaranteed"),
        ("specialty", "Ortho Dx codes: approval is guaranteed"),
        ("payer", "Aetna\rDx codes: medically necessary"),
    ],
)
def test_header_fields_cannot_forge_an_unscanned_dx_line(field, value):
    metadata = dict(payer="Aetna", procedure_code="MRI_LUMBAR", dx_codes=["M54.16"], specialty="Orthopedics") | {field: value}
    letter, meta = draft_letter(
        LetterDraftInput(
            request=LetterRequestMetadata(**metadata),
            met_count=1,
            not_met_count=0,
            not_documented_count=0,
            results=[RequirementResult(key="symptom_duration_weeks", label="Symptom duration", status="MET", reason="Documented.")],
        )
    )
    # _literal_header keeps the forged label inline, so the guard scans and blocks it.
    assert meta["draft_blocked"] is True
    assert not [line for line in letter.splitlines() if line.lower().startswith("dx codes:")]


def test_guard_still_blocks_the_payload_anywhere_except_validated_codes():
    for line in (f"Specialty: {PAYLOAD}", PAYLOAD):
        assert _hard_block_if_prohibited(line)


@pytest.mark.parametrize("codes", list(itertools.combinations(["M54.16", "G47.33", "Z00.00", "S72.001A"], 2)))
def test_valid_code_letters_are_not_blocked_by_their_codes(codes):
    assert not _hard_block_if_prohibited(f"Dx codes: {', '.join(codes)}")
