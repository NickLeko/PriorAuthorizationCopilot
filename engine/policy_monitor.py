from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Governance-only module:
# - Detects drift in official policy sources
# - Writes snapshots/diffs/logs
# - Does NOT modify rules, outcomes, or inference semantics


DEFAULT_SOURCES_YAML = Path("rules/policy_sources.yaml")
DEFAULT_SNAPSHOT_ROOT = Path("policy_snapshots")
DEFAULT_LOG_PATH = DEFAULT_SNAPSHOT_ROOT / "drift_log.jsonl"


@dataclass(frozen=True)
class PolicySource:
    id: str
    payer: str
    procedure_code: str
    url: str
    source_type: str
    trust_level: str
    check_frequency: str
    owner: str
    notes: str = ""


def utc_now_iso() -> str:
    # RFC3339-ish (Z)
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def load_policy_sources(path: Path = DEFAULT_SOURCES_YAML) -> List[PolicySource]:
    if not path.exists():
        raise FileNotFoundError(f"Missing policy sources registry: {path.as_posix()}")

    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "PyYAML is required to load rules/policy_sources.yaml. "
            "Install pyyaml or vendor a minimal YAML loader."
        ) from e

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "sources" not in data:
        raise ValueError("policy_sources.yaml must be a mapping with a top-level 'sources' list")

    sources_raw = data.get("sources")
    if not isinstance(sources_raw, list):
        raise ValueError("'sources' must be a list")

    out: List[PolicySource] = []
    for s in sources_raw:
        if not isinstance(s, dict):
            continue
        missing = [k for k in ("id", "payer", "procedure_code", "url", "source_type", "trust_level", "check_frequency", "owner") if k not in s]
        if missing:
            raise ValueError(f"Source entry missing fields {missing}: {s}")
        out.append(
            PolicySource(
                id=str(s["id"]),
                payer=str(s["payer"]),
                procedure_code=str(s["procedure_code"]),
                url=str(s["url"]),
                source_type=str(s["source_type"]),
                trust_level=str(s["trust_level"]),
                check_frequency=str(s["check_frequency"]),
                owner=str(s["owner"]),
                notes=str(s.get("notes", "")),
            )
        )
    return out


def fetch_policy(url: str, timeout_s: int = 15) -> str:
    """
    Fetch raw policy content.
    Note: tests must NOT call this (offline fixtures only).
    """
    try:
        import requests  # type: ignore
    except Exception as e:
        raise RuntimeError("requests is required for live fetches (not used in tests).") from e

    headers = {
        "User-Agent": "PriorAuthorizationCopilot/PolicyMonitor (+governance; contact owner in policy_sources.yaml)"
    }
    resp = requests.get(url, headers=headers, timeout=timeout_s)
    resp.raise_for_status()
    # Keep as text; normalization will reduce noise.
    return resp.text


class _HTMLTextExtractor:
    """
    Minimal, deterministic HTML -> text extractor.
    Avoids LLMs and avoids fragile DOM dependence.
    """

    def __init__(self) -> None:
        self._chunks: List[str] = []
        self._skip_depth: int = 0

    def feed(self, html: str) -> None:
        # We avoid bs4 dependency: regex-based stripping + conservative block handling.
        # 1) remove script/style blocks entirely
        html = re.sub(r"(?is)<script\b.*?>.*?</script>", " ", html)
        html = re.sub(r"(?is)<style\b.*?>.*?</style>", " ", html)
        # 2) remove noscript
        html = re.sub(r"(?is)<noscript\b.*?>.*?</noscript>", " ", html)
        # 3) convert common block tags into newlines
        html = re.sub(r"(?is)</(p|div|li|ul|ol|h1|h2|h3|h4|h5|h6|br|tr|section|article)>", "\n", html)
        html = re.sub(r"(?is)<(p|div|li|ul|ol|h1|h2|h3|h4|h5|h6|br|tr|section|article)\b.*?>", "\n", html)
        # 4) strip remaining tags
        html = re.sub(r"(?is)<[^>]+>", " ", html)
        # 5) unescape basic entities (minimal; deterministic)
        html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
        self._chunks.append(html)

    def text(self) -> str:
        return "\n".join(self._chunks)


_BOILERPLATE_PATTERNS = [
    r"^\s*cookie(s)?\s+policy\s*$",
    r"^\s*privacy\s+policy\s*$",
    r"^\s*terms\s+of\s+use\s*$",
    r"^\s*contact\s+us\s*$",
    r"^\s*site\s+map\s*$",
    r"^\s*search\s*$",
    r"^\s*back\s+to\s+top\s*$",
]


def normalize_policy(raw: str) -> str:
    """
    Goal: stable hash + fewer false diffs.
    Strategy:
      - If HTML-ish: strip scripts/styles, extract text, force line structure.
      - Normalize whitespace and punctuation.
      - Drop obvious boilerplate/navigation lines.
      - Keep headings/list-like content.
    Deterministic by construction.
    """
    raw = raw or ""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    looks_like_html = bool(re.search(r"(?i)<(html|body|div|p|h1|h2|h3|ul|ol|li|table|tr|td)\b", raw))
    if looks_like_html:
        extractor = _HTMLTextExtractor()
        extractor.feed(raw)
        text = extractor.text()
    else:
        text = raw

    # Normalize unicode-ish quirks minimally
    text = text.replace("\u00a0", " ")  # nbsp
    text = text.replace("•", "-")

    # Split into lines, trim, collapse internal whitespace
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]

    cleaned: List[str] = []
    for ln in lines:
        if not ln:
            continue

        low = ln.lower()

        # Drop boilerplate-y lines
        if any(re.match(pat, low) for pat in _BOILERPLATE_PATTERNS):
            continue

        # Drop very short nav crumbs
        if len(ln) <= 2:
            continue

        # Drop "breadcrumb" style separators
        if re.fullmatch(r"[-|•=]{3,}", ln):
            continue

        cleaned.append(ln)

    # De-duplicate consecutive identical lines (common in nav/footer repeats)
    deduped: List[str] = []
    prev = None
    for ln in cleaned:
        if ln == prev:
            continue
        deduped.append(ln)
        prev = ln

    # Final: join as stable newline-separated text
    normalized = "\n".join(deduped).strip() + "\n"
    return normalized


def hash_text(text: str) -> str:
    h = hashlib.sha256()
    h.update((text or "").encode("utf-8"))
    return h.hexdigest()


def _source_dir(root: Path, source_id: str) -> Path:
    return root / source_id


def _latest_snapshot_path(root: Path, source_id: str) -> Path:
    return _source_dir(root, source_id) / "latest.json"


def _history_snapshot_path(root: Path, source_id: str, ts: str) -> Path:
    return _source_dir(root, source_id) / "history" / f"{ts}.json"


def _diff_path(root: Path, source_id: str, ts: str) -> Path:
    return _source_dir(root, source_id) / "diffs" / f"{ts}.patch"


def read_latest_snapshot(root: Path, source_id: str) -> Optional[Dict[str, Any]]:
    p = _latest_snapshot_path(root, source_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def diff_text(old_text: str, new_text: str, fromfile: str = "old", tofile: str = "new") -> str:
    old_lines = (old_text or "").splitlines(keepends=True)
    new_lines = (new_text or "").splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=fromfile, tofile=tofile)
    return "".join(diff)


def write_snapshot(
    source: PolicySource,
    normalized_text: str,
    content_hash: str,
    fetched_at_utc: str,
    snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT,
) -> Dict[str, str]:
    """
    Writes latest + history snapshot (normalized text only).
    Returns paths (as strings).
    """
    src_dir = _source_dir(snapshot_root, source.id)
    _safe_mkdir(src_dir)
    _safe_mkdir(src_dir / "history")
    _safe_mkdir(src_dir / "diffs")

    snap = {
        "id": source.id,
        "payer": source.payer,
        "procedure_code": source.procedure_code,
        "url": source.url,
        "fetched_at_utc": fetched_at_utc,
        "content_hash_sha256": content_hash,
        "normalized_text": normalized_text,
    }

    ts = fetched_at_utc.replace(":", "").replace("-", "")
    # e.g. 20260206T031210Z -> keep 'T' and 'Z' (already no colons)
    history_path = _history_snapshot_path(snapshot_root, source.id, ts)
    latest_path = _latest_snapshot_path(snapshot_root, source.id)

    history_path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "latest_snapshot_path": latest_path.as_posix(),
        "history_snapshot_path": history_path.as_posix(),
    }


def append_drift_log(entry: Dict[str, Any], log_path: Path = DEFAULT_LOG_PATH) -> None:
    _safe_mkdir(log_path.parent)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def check_sources(
    sources: List[PolicySource],
    *,
    write_artifacts: bool = True,
    snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT,
    now_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """
    For each source:
      - fetch -> normalize -> hash
      - compare against latest snapshot hash
      - if changed:
          - write latest+history snapshot
          - write unified diff patch
          - append drift log
          - return REVIEW_REQUIRED
    """
    detected_at = now_utc or utc_now_iso()
    changes: List[Dict[str, Any]] = []

    for src in sources:
        raw = fetch_policy(src.url)
        normalized = normalize_policy(raw)
        new_hash = hash_text(normalized)

        latest = read_latest_snapshot(snapshot_root, src.id)
        old_hash = (latest or {}).get("content_hash_sha256")
        old_text = (latest or {}).get("normalized_text", "")

        changed = (old_hash is not None) and (str(old_hash) != new_hash)
        first_seen = old_hash is None

        status = "OK"
        latest_snapshot_path = _latest_snapshot_path(snapshot_root, src.id).as_posix()
        diff_path: Optional[str] = None

        if write_artifacts:
            # Always write a snapshot on first run (bootstrap)
            if first_seen:
                write_snapshot(src, normalized, new_hash, detected_at, snapshot_root=snapshot_root)
                append_drift_log(
                    {
                        "detected_at_utc": detected_at,
                        "id": src.id,
                        "payer": src.payer,
                        "procedure_code": src.procedure_code,
                        "url": src.url,
                        "event": "BOOTSTRAP_SNAPSHOT_CREATED",
                        "old_hash": None,
                        "new_hash": new_hash,
                    }
                )

            elif changed:
                status = "REVIEW_REQUIRED"
                # write snapshot first
                paths = write_snapshot(src, normalized, new_hash, detected_at, snapshot_root=snapshot_root)

                # write diff patch
                ts = detected_at.replace(":", "").replace("-", "")
                patch = diff_text(old_text, normalized, fromfile="previous", tofile="current")
                patch_path = _diff_path(snapshot_root, src.id, ts)
                patch_path.write_text(patch, encoding="utf-8")
                diff_path = patch_path.as_posix()

                append_drift_log(
                    {
                        "detected_at_utc": detected_at,
                        "id": src.id,
                        "payer": src.payer,
                        "procedure_code": src.procedure_code,
                        "url": src.url,
                        "event": "POLICY_DRIFT_DETECTED",
                        "old_hash": old_hash,
                        "new_hash": new_hash,
                        "latest_snapshot_path": paths["latest_snapshot_path"],
                        "diff_path": diff_path,
                        "status": status,
                    }
                )

        else:
            # No writes: still report drift based on hashes
            if first_seen:
                status = "UNKNOWN_BASELINE"  # can't conclude drift without baseline
            elif changed:
                status = "REVIEW_REQUIRED"

        changes.append(
            {
                "id": src.id,
                "payer": src.payer,
                "procedure_code": src.procedure_code,
                "url": src.url,
                "changed": bool(changed),
                "old_hash": old_hash,
                "new_hash": new_hash,
                "latest_snapshot_path": latest_snapshot_path,
                "diff_path": diff_path,
                "status": status,
            }
        )

    return {"detected_at_utc": detected_at, "changes": changes}


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Policy Drift + Rule Governance Monitor (governance-only).")
    ap.add_argument("--sources", type=str, default=str(DEFAULT_SOURCES_YAML), help="Path to rules/policy_sources.yaml")
    ap.add_argument("--snapshot-root", type=str, default=str(DEFAULT_SNAPSHOT_ROOT), help="Snapshot root directory")
    ap.add_argument("--write", action="store_true", help="Write snapshots/diffs/logs (bootstrap + drift artifacts)")
    ap.add_argument("--check", action="store_true", help="Check sources (default if neither --write nor --check is set)")
    args = ap.parse_args()

    sources_path = Path(args.sources)
    snapshot_root = Path(args.snapshot_root)
    sources = load_policy_sources(sources_path)

    write_artifacts = bool(args.write)
    if not (args.write or args.check):
        # default: check without writing (safe)
        write_artifacts = False

    report = check_sources(sources, write_artifacts=write_artifacts, snapshot_root=snapshot_root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
