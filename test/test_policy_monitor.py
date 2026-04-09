from __future__ import annotations

from pathlib import Path

from engine.policy_monitor import (
    PolicySource,
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
    assert Path(paths["latest_snapshot_path"]).name == "latest.json"
