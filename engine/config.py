from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(raw_path: str, repo_root: Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    repo_root: Path
    rules_path: Path
    provenance_path: Path
    policy_sources_path: Path
    rulebook_manifest_path: Path
    snapshot_root: Path
    synthetic_cases_path: Path
    docs_artifacts_dir: Path
    log_level: str = "WARNING"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    allowed_sites: List[str] = Field(default_factory=lambda: ["outpatient", "inpatient", "ASC", "office"])

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in VALID_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(VALID_LOG_LEVELS)}")
        return normalized

    @field_validator("api_host")
    @classmethod
    def _strip_api_host(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("api_host must be non-empty.")
        return stripped

    @field_validator("api_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if value <= 0 or value > 65535:
            raise ValueError("api_port must be between 1 and 65535.")
        return value

    @field_validator("allowed_sites")
    @classmethod
    def _validate_allowed_sites(cls, value: List[str]) -> List[str]:
        sites = [site.strip() for site in value if site.strip()]
        if not sites:
            raise ValueError("allowed_sites must contain at least one site.")
        return sites

    @model_validator(mode="after")
    def _validate_required_paths(self) -> "AppConfig":
        required_files = {
            "rules_path": self.rules_path,
            "provenance_path": self.provenance_path,
            "policy_sources_path": self.policy_sources_path,
            "rulebook_manifest_path": self.rulebook_manifest_path,
            "synthetic_cases_path": self.synthetic_cases_path,
        }
        for field_name, path in required_files.items():
            if not path.exists():
                raise ValueError(f"{field_name} does not exist: {path}")
        return self


def load_app_config(base_dir: Path | None = None) -> AppConfig:
    repo_root = (base_dir or _repo_root_from_file()).resolve()

    return AppConfig(
        repo_root=repo_root,
        rules_path=_resolve_path(os.getenv("PA_COPILOT_RULES_PATH", "rules/payer_rules.yaml"), repo_root),
        provenance_path=_resolve_path(os.getenv("PA_COPILOT_PROVENANCE_PATH", "rules/provenance.yaml"), repo_root),
        policy_sources_path=_resolve_path(os.getenv("PA_COPILOT_POLICY_SOURCES_PATH", "rules/policy_sources.yaml"), repo_root),
        rulebook_manifest_path=_resolve_path(
            os.getenv("PA_COPILOT_RULEBOOK_MANIFEST_PATH", "rulebook/manifest.yaml"),
            repo_root,
        ),
        snapshot_root=_resolve_path(os.getenv("PA_COPILOT_SNAPSHOT_ROOT", "policy_snapshots"), repo_root),
        synthetic_cases_path=_resolve_path(os.getenv("PA_COPILOT_SYNTHETIC_CASES_PATH", "inputs/synthetic_cases.json"), repo_root),
        docs_artifacts_dir=_resolve_path(os.getenv("PA_COPILOT_ARTIFACTS_DIR", "docs/artifacts"), repo_root),
        log_level=os.getenv("PA_COPILOT_LOG_LEVEL", "WARNING"),
        api_host=os.getenv("PA_COPILOT_API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("PA_COPILOT_API_PORT", "8000")),
    )
