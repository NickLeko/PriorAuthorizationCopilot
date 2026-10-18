"""Payload-free experiment failures. Never convert these into missing facts."""

from typing import Literal

FailureCode = Literal[
    "INVALID_RECORDED_RESPONSE",
    "RECORDED_EXTRACTION_FAILURE",
    "INVALID_PROPOSAL",
    "NOTE_MISMATCH",
    "MISSING_RECORDING",
    "MALFORMED_RECORDING",
    "RECORDING_INTEGRITY_FAILURE",
    "RECORDING_IDENTITY_FAILURE",
    "RECORDING_NOTE_MISMATCH",
    "INVALID_RECORDING_MANIFEST",
    "INVALID_FROZEN_BASELINE",
    "EXPERIMENT_CONTEXT_CHANGED",
    "EVALUATION_FAILURE",
]


class ExperimentFailure(ValueError):
    def __init__(self, code: FailureCode):
        self.code = code
        super().__init__(code)
