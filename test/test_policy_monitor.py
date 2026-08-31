from __future__ import annotations

from pathlib import Path

import pytest

import engine.policy_monitor as policy_monitor
from engine.policy_monitor import (
    PolicySource,
    SnapshotValidationError,
    check_sources,
    diff_text,
    hash_text,
    normalize_policy,
    read_latest_snapshot,
    write_snapshot,
)

# Repo uses "test/fixtures", not "tests/fixtures"
FIXTURE_PATH = Path("test/fixtures/policy_aetna_0157_sample.html")


def test_normalization_is_deterministic():
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    n1 = normalize_policy(raw)
    n2 = normalize_policy(raw)
    assert n1 == n2
    assert n1.endswith("\n")
    # Should remove obvious boilerplate
    assert "Privacy Policy" not in n1
    assert "Terms of Use" not in n1
    assert "Cookie Policy" not in n1


def test_hash_changes_when_content_changes():
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    n1 = normalize_policy(raw)
    h1 = hash_text(n1)

    # Simulate an official change (e.g., "6 weeks" -> "8 weeks")
    raw_changed = raw.replace("at least 6 weeks", "at least 8 weeks")
    n2 = normalize_policy(raw_changed)
    h2 = hash_text(n2)

    assert h1 != h2


def test_diff_contains_expected_line():
    old = "Line A\nSymptoms are present for at least 6 weeks\nLine C\n"
    new = "Line A\nSymptoms are present for at least 8 weeks\nLine C\n"
    patch = diff_text(old, new, fromfile="previous", tofile="current")
    assert "--- previous" in patch
    assert "+++ current" in patch
    assert "-Symptoms are present for at least 6 weeks" in patch
    assert "+Symptoms are present for at least 8 weeks" in patch


def test_write_snapshot_and_read_latest(tmp_path: Path):
    src = PolicySource(
        id="aetna_mri_lumbar",
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        url="https://example.invalid/0157.html",
        source_name="Fixture Policy Source",
        source_type="official_policy_web",
        trust_level="verified",
        check_frequency="daily",
        owner="NickLeko",
        notes="fixture test",
    )

    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    normalized = normalize_policy(raw)
    h = hash_text(normalized)

    fetched_at = "2026-02-06T03:12:10Z"
    paths = write_snapshot(src, normalized, h, fetched_at, snapshot_root=tmp_path)

    latest = read_latest_snapshot(tmp_path, src.id)
    assert latest is not None
    assert latest["id"] == src.id
    assert latest["content_hash_sha256"] == h
    assert "normalized_text" in latest
    assert latest["last_checked_utc"] == fetched_at
    assert Path(paths["latest_snapshot_path"]).name == "latest.json"


def test_snapshot_hash_is_recomputed_on_read(tmp_path: Path):
    src = _fixture_source()
    normalized = "verified normalized policy content\n"
    write_snapshot(src, normalized, hash_text(normalized), "2026-08-20T00:00:00Z", snapshot_root=tmp_path)
    latest_path = tmp_path / src.id / "latest.json"
    payload = policy_monitor.json.loads(latest_path.read_text(encoding="utf-8"))
    payload["normalized_text"] = "tampered content\n"
    latest_path.write_text(policy_monitor.json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotValidationError, match="does not match"):
        read_latest_snapshot(tmp_path, src.id, source=src)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"id": "fixture"},
        {
            "id": "fixture",
            "payer": "Aetna",
            "procedure_code": "MRI_LUMBAR",
            "url": "https://example.invalid/policy",
            "fetched_at_utc": "not-a-date",
            "content_hash_sha256": "0" * 64,
            "normalization": "engine.policy_monitor.normalize_policy:v1",
            "normalized_text": "content\n",
        },
    ],
)
def test_malformed_snapshot_structures_are_rejected(tmp_path: Path, payload):
    snapshot_dir = tmp_path / "fixture"
    snapshot_dir.mkdir(parents=True)
    snapshot_dir.joinpath("latest.json").write_text(policy_monitor.json.dumps(payload), encoding="utf-8")

    with pytest.raises(SnapshotValidationError):
        read_latest_snapshot(tmp_path, "fixture")


def test_write_snapshot_rejects_caller_supplied_hash_mismatch(tmp_path: Path):
    with pytest.raises(SnapshotValidationError, match="mismatched content hash"):
        write_snapshot(
            _fixture_source(),
            "normalized content\n",
            "0" * 64,
            "2026-08-20T00:00:00Z",
            snapshot_root=tmp_path,
        )


def test_unchanged_successful_check_refreshes_last_checked_without_rewriting_content_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    src = _fixture_source()
    raw = "Policy criterion remains six weeks."
    normalized = normalize_policy(raw)
    write_snapshot(src, normalized, hash_text(normalized), "2026-08-01T00:00:00Z", snapshot_root=tmp_path)
    history_before = list((tmp_path / src.id / "history").iterdir())
    monkeypatch.setattr(policy_monitor, "fetch_policy", lambda _url: raw)

    report = check_sources(
        [src],
        write_artifacts=True,
        snapshot_root=tmp_path,
        now_utc="2026-08-30T00:00:00Z",
    )
    latest = read_latest_snapshot(tmp_path, src.id, source=src)

    assert report["changes"][0]["status"] == "OK"
    assert latest is not None
    assert latest["fetched_at_utc"] == "2026-08-01T00:00:00Z"
    assert latest["last_checked_utc"] == "2026-08-30T00:00:00Z"
    assert list((tmp_path / src.id / "history").iterdir()) == history_before


def _fixture_source() -> PolicySource:
    return PolicySource(
        id="fixture",
        payer="Aetna",
        procedure_code="MRI_LUMBAR",
        url="https://example.invalid/policy",
        source_name="Fixture Policy Source",
        source_type="official_policy_web",
        trust_level="verified",
        check_frequency="monthly",
        owner="owner",
    )
