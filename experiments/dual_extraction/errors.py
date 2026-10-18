"""Payload-free experiment failures. Never convert these into missing facts."""

from typing import Literal

FailureCode = Literal["INVALID_RECORDED_RESPONSE", "RECORDED_EXTRACTION_FAILURE", "INVALID_PROPOSAL", "NOTE_MISMATCH"]


class ExperimentFailure(ValueError):
    def __init__(self, code: FailureCode):
        self.code = code
        super().__init__(code)
