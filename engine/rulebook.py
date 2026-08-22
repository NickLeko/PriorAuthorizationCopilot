from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from .schemas import RulebookDiffResponse, RulebookFileSet, RulebookRelease, RulebookStatusResponse


class RulebookError(Exception):
    pass


def _load_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise RulebookError(f"YAML file must contain a mapping: {path.as_posix()}")
    return payload


def _resolve_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _display_path(repo_root: Path, raw_path: str) -> str:
    resolved = _resolve_path(repo_root, raw_path)
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def load_rulebook_manifest(path: Path) -> Dict[str, Any]:
    manifest = _load_yaml(path)
    if "stages" not in manifest or "releases" not in manifest:
        raise RulebookError("rulebook manifest must include 'stages' and 'releases'")
    if not isinstance(manifest["stages"], dict):
        raise RulebookError("rulebook manifest 'stages' must be a mapping")
    if not isinstance(manifest["releases"], dict):
        raise RulebookError("rulebook manifest 'releases' must be a mapping")
    return manifest


def _extract_procedure_map(rules_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for payer, payer_config in (rules_data.get("payers") or {}).items():
        for procedure_code, procedure in (payer_config.get("procedures") or {}).items():
            out[f"{payer}:{procedure_code}"] = procedure
    return out


def _extract_procedure_codes(rules_data: Dict[str, Any]) -> list[str]:
    return sorted(_extract_procedure_map(rules_data))


def _extract_provenance_map(provenance_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for payer, payer_entries in (provenance_data.get("sources") or {}).items():
        for procedure_code, entry in (payer_entries or {}).items():
            out[f"{payer}:{procedure_code}"] = entry
    return out


def _extract_policy_source_map(policy_sources_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for source in policy_sources_data.get("sources") or []:
        if not isinstance(source, dict):
            continue
        out[str(source.get("id") or "")] = source
    return {key: value for key, value in out.items() if key}


def _load_release_bundle(
    repo_root: Path,
    raw_release: Dict[str, Any],
) -> Tuple[RulebookFileSet, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    files = raw_release.get("files") or {}
    if not isinstance(files, dict):
        raise RulebookError("rulebook release 'files' must be a mapping")

    rules_path = _resolve_path(repo_root, str(files.get("rules") or ""))
    provenance_path = _resolve_path(repo_root, str(files.get("provenance") or ""))
    policy_sources_path = _resolve_path(repo_root, str(files.get("policy_sources") or ""))
    bundle = RulebookFileSet(
        rules_path=_display_path(repo_root, str(files.get("rules") or "")),
        provenance_path=_display_path(repo_root, str(files.get("provenance") or "")),
        policy_sources_path=_display_path(repo_root, str(files.get("policy_sources") or "")),
    )

    return (
        bundle,
        _load_yaml(rules_path),
        _load_yaml(provenance_path),
        _load_yaml(policy_sources_path),
    )


def get_rulebook_status(repo_root: Path, manifest_path: Path, runtime_files: RulebookFileSet) -> RulebookStatusResponse:
    manifest = load_rulebook_manifest(manifest_path)
    stages = manifest.get("stages") or {}
    releases_raw = manifest.get("releases") or {}
    validation_errors: list[str] = []

    for required_stage in ("draft", "reviewed", "active"):
        if required_stage not in stages:
            validation_errors.append(f"Missing stage assignment for '{required_stage}'.")

    runtime_rules = _load_yaml(Path(runtime_files.rules_path))
    runtime_provenance = _load_yaml(Path(runtime_files.provenance_path))
    runtime_policy_sources = _load_yaml(Path(runtime_files.policy_sources_path))

    releases: list[RulebookRelease] = []
    active_release_id = stages.get("active")

    for release_id, raw_release in sorted(releases_raw.items()):
        if not isinstance(raw_release, dict):
            validation_errors.append(f"Release '{release_id}' must be a mapping.")
            continue

        try:
            file_set, rules_data, provenance_data, policy_sources_data = _load_release_bundle(repo_root, raw_release)
        except Exception as exc:
            validation_errors.append(f"Release '{release_id}' could not be loaded: {exc}")
            continue

        procedures = _extract_procedure_codes(rules_data)
        declared_procedures = sorted(str(item) for item in raw_release.get("procedures") or [])
        if declared_procedures and declared_procedures != procedures:
            validation_errors.append(f"Release '{release_id}' declared procedures {declared_procedures} but files contain {procedures}.")

        file_rules_version = str(rules_data.get("version")) if rules_data.get("version") is not None else None
        declared_rules_version = str(raw_release.get("rules_version")) if raw_release.get("rules_version") is not None else None
        if declared_rules_version and declared_rules_version != file_rules_version:
            validation_errors.append(
                f"Release '{release_id}' declared rules_version={declared_rules_version} but files contain {file_rules_version}."
            )

        runtime_matches = None
        if release_id == active_release_id:
            runtime_matches = (
                rules_data == runtime_rules and provenance_data == runtime_provenance and policy_sources_data == runtime_policy_sources
            )
            if not runtime_matches:
                validation_errors.append(f"Active release '{release_id}' does not match the runtime files under rules/.")

        releases.append(
            RulebookRelease(
                release_id=str(release_id),
                stage=raw_release.get("stage"),
                summary=str(raw_release.get("summary") or release_id),
                created_at=raw_release.get("created_at"),
                based_on_release_id=raw_release.get("based_on_release_id"),
                rules_version=declared_rules_version or file_rules_version,
                procedures=declared_procedures or procedures,
                files=file_set,
                reviewer=raw_release.get("reviewer"),
                reviewed_at=raw_release.get("reviewed_at"),
                runtime_matches=runtime_matches,
                notes=[str(note) for note in raw_release.get("notes") or []],
            )
        )

    for stage_name, release_id in stages.items():
        if release_id and release_id not in releases_raw:
            validation_errors.append(f"Stage '{stage_name}' points to unknown release '{release_id}'.")

    return RulebookStatusResponse(
        manifest_version=str(manifest.get("version")) if manifest.get("version") is not None else None,
        active_release_id=str(active_release_id) if active_release_id else None,
        stage_assignments={str(key): (str(value) if value else None) for key, value in stages.items()},
        runtime_rules_version=str(runtime_rules.get("version")) if runtime_rules.get("version") is not None else None,
        releases=releases,
        validation_errors=validation_errors,
    )


def get_rulebook_diff(repo_root: Path, manifest_path: Path, from_release_id: str, to_release_id: str) -> RulebookDiffResponse:
    manifest = load_rulebook_manifest(manifest_path)
    releases_raw = manifest.get("releases") or {}

    if from_release_id not in releases_raw:
        raise RulebookError(f"Unknown rulebook release: {from_release_id}")
    if to_release_id not in releases_raw:
        raise RulebookError(f"Unknown rulebook release: {to_release_id}")

    _, from_rules, from_provenance, from_policy_sources = _load_release_bundle(repo_root, releases_raw[from_release_id])
    _, to_rules, to_provenance, to_policy_sources = _load_release_bundle(repo_root, releases_raw[to_release_id])

    from_procedure_map = _extract_procedure_map(from_rules)
    to_procedure_map = _extract_procedure_map(to_rules)
    from_procedures = set(from_procedure_map)
    to_procedures = set(to_procedure_map)

    added_procedures = sorted(to_procedures - from_procedures)
    removed_procedures = sorted(from_procedures - to_procedures)
    changed_procedures = sorted(
        procedure_code
        for procedure_code in (from_procedures & to_procedures)
        if from_procedure_map[procedure_code] != to_procedure_map[procedure_code]
    )

    from_provenance_map = _extract_provenance_map(from_provenance)
    to_provenance_map = _extract_provenance_map(to_provenance)
    changed_provenance = sorted(
        procedure_code
        for procedure_code in set(from_provenance_map) | set(to_provenance_map)
        if from_provenance_map.get(procedure_code) != to_provenance_map.get(procedure_code)
    )

    from_policy_map = _extract_policy_source_map(from_policy_sources)
    to_policy_map = _extract_policy_source_map(to_policy_sources)
    changed_policy_sources = sorted(
        source_id
        for source_id in set(from_policy_map) | set(to_policy_map)
        if from_policy_map.get(source_id) != to_policy_map.get(source_id)
    )

    rules_version_from = str(from_rules.get("version")) if from_rules.get("version") is not None else None
    rules_version_to = str(to_rules.get("version")) if to_rules.get("version") is not None else None

    def _format_summary_line(label: str, values: list[str]) -> str:
        return f"{label}: {', '.join(values)}" if values else f"{label}: none"

    summary_lines = [
        f"Rules version: {rules_version_from or 'n/a'} -> {rules_version_to or 'n/a'}",
        _format_summary_line("Added procedures", added_procedures),
        _format_summary_line("Removed procedures", removed_procedures),
        _format_summary_line("Changed procedures", changed_procedures),
        _format_summary_line("Changed provenance entries", changed_provenance),
        _format_summary_line("Changed policy source entries", changed_policy_sources),
    ]

    return RulebookDiffResponse(
        from_release_id=from_release_id,
        to_release_id=to_release_id,
        from_stage=releases_raw[from_release_id].get("stage"),
        to_stage=releases_raw[to_release_id].get("stage"),
        rules_version_from=rules_version_from,
        rules_version_to=rules_version_to,
        added_procedures=added_procedures,
        removed_procedures=removed_procedures,
        changed_procedures=changed_procedures,
        changed_provenance=changed_provenance,
        changed_policy_sources=changed_policy_sources,
        summary_lines=summary_lines,
    )
