import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from scripts import audit_dependencies as audit

TODAY = date(2026, 10, 21)
ROOT = Path(__file__).resolve().parents[1]
CVE = "CVE-2026-112897"


def entry(**changes):
    return {"package": "pillow", "reason": "Reviewed text-only application; see security review.", "expires": "2026-11-04"} | changes


def load(tmp_path, payload, *, today=TODAY):
    path = tmp_path / "exceptions.json"
    path.write_text(json.dumps(payload))
    return audit.load_exceptions(path, today=today)


def report(name="pillow", version="12.3.0", identity=CVE, aliases=None):
    return {
        "dependencies": [
            {"name": name, "version": version, "vulns": [{"id": identity, "aliases": aliases or [], "fix_versions": ["13.0.0"]}]}
        ]
    }


@pytest.mark.parametrize("cve", sorted(audit.PILLOW_CVES))
def test_each_authorized_pillow_exception_and_alias_is_visible(tmp_path, capsys, cve):
    exceptions = load(tmp_path, {cve: entry()})
    assert audit.report_findings(report(identity=cve), exceptions) == 0
    assert audit.report_findings(report(identity="GHSA-test", aliases=[cve]), exceptions) == 0
    output = capsys.readouterr().out
    assert f"ACTIVE EXCEPTION pillow {cve}" in output
    assert "2026-11-04" in output
    assert entry()["reason"] in output
    assert "EXCEPTED pillow==12.3.0 GHSA-test" in output


def test_repository_exceptions_preserve_seven_starlette_entries():
    current = audit.load_exceptions(ROOT / "security/pip-audit-ignores.json", today=TODAY)
    assert set(current) == audit.STARLETTE_CVES | audit.PILLOW_CVES
    for cve in audit.STARLETTE_CVES:
        assert current[cve]["package"] == "starlette"
        assert "expires" not in current[cve]
        assert audit.report_findings(report("starlette", "0.46.2", "PYSEC-test", [cve]), current) == 0
    assert all(current[cve]["expires"] == "2026-11-04" for cve in audit.PILLOW_CVES)


@pytest.mark.parametrize("today", [date(2026, 11, 4), date(2026, 11, 5), date(2027, 1, 1)])
def test_expiration_fails_on_or_after_utc_deadline(tmp_path, today):
    with pytest.raises(ValueError, match="expired"):
        load(tmp_path, {CVE: entry()}, today=today)


def test_day_before_expiration_is_authorized(tmp_path):
    assert load(tmp_path, {CVE: entry()}, today=date(2026, 11, 3))


@pytest.mark.parametrize(
    "bad_entry",
    [
        None,
        [],
        "reason",
        {},
        {"package": "pillow", "reason": "reviewed"},
        {"reason": "reviewed", "expires": "2026-11-04"},
        entry(package="starlette"),
        entry(package="Pillow"),
        entry(reason=" \n\t"),
        entry(reason=None),
        entry(reason=1),
        entry(expires=None),
        entry(expires=20261104),
        entry(expires="2026-02-30"),
        entry(expires="20261104"),
        entry(expires="2026-11-4"),
        entry(expires="2026-11-04T23:59:59Z"),
        entry(expires="2026-11-05"),
        entry(ignore_all=True),
    ],
)
def test_malformed_exception_fails_closed(tmp_path, bad_entry):
    with pytest.raises(ValueError):
        load(tmp_path, {CVE: bad_entry})


@pytest.mark.parametrize("payload", [[], None, "ignored", {"CVE-2026-999999": entry()}, {"GHSA-test": entry()}])
def test_unrecognized_exception_or_container_fails_closed(tmp_path, payload):
    with pytest.raises(ValueError):
        load(tmp_path, payload)


@pytest.mark.parametrize("content", ['{"a":1,"a":2}', '{"CVE-2026-112897":{"package":"pillow","package":"pillow"}}', "{"])
def test_duplicate_keys_and_invalid_json_fail_closed(tmp_path, content):
    path = tmp_path / "exceptions.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        audit.load_exceptions(path, today=TODAY)


@pytest.mark.parametrize(
    "finding",
    [report(identity="CVE-2026-999999"), report(name="another-package"), report(version="12.2.0"), report(version="13.0.0")],
)
def test_other_cves_packages_and_pillow_versions_remain_blocking(tmp_path, capsys, finding):
    assert audit.report_findings(finding, load(tmp_path, {CVE: entry()})) == 1
    assert "UNRESOLVED" in capsys.readouterr().out


def test_mixed_report_keeps_unrecognized_findings_blocking(tmp_path):
    mixed = report()
    mixed["dependencies"].extend(report(name="certifi", version="2026.10.19", identity="CVE-2026-999999")["dependencies"])
    assert audit.report_findings(mixed, load(tmp_path, {CVE: entry()})) == 1
    assert audit.report_findings(report(), {}) == 1
    assert audit.report_findings({"dependencies": [{"name": "certifi", "version": "2026.10.19", "vulns": []}]}, {}) == 0


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"dependencies": {}},
        {"dependencies": [None]},
        {"dependencies": [{"name": "pillow", "version": "12.3.0", "skip_reason": "unavailable"}]},
        {"dependencies": [{"name": "pillow", "version": "12.3.0", "vulns": [None]}]},
        report(aliases="CVE-2026-112897"),
    ],
)
def test_malformed_or_skipped_report_fails_closed(payload):
    with pytest.raises(ValueError):
        audit.report_findings(payload, {})


def test_cli_runs_strict_unsuppressed_lock_audit_and_propagates_result(monkeypatch):
    monkeypatch.setattr(audit, "load_exceptions", lambda path: {})
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, json.dumps(report()), "Found 1 known vulnerability\n")

    monkeypatch.setattr(audit.subprocess, "run", run)
    assert audit.main() == 1
    assert "--strict" in commands[0] and "--disable-pip" in commands[0]
    assert str(ROOT / "requirements.lock") in commands[0]
    assert "--ignore-vuln" not in commands[0]


@pytest.mark.parametrize("status,output", [(2, ""), (1, ""), (0, "{}"), (1, '{"dependencies":[]}')])
def test_cli_operational_failures_cannot_become_success(monkeypatch, status, output):
    monkeypatch.setattr(audit, "load_exceptions", lambda path: {})
    monkeypatch.setattr(
        audit.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], status, output, "service error\n")
    )
    assert audit.main() != 0


def test_cli_checks_expiry_before_even_a_clean_scan(monkeypatch, tmp_path, capsys):
    real_load = audit.load_exceptions
    path = tmp_path / "expired.json"
    path.write_text(json.dumps({CVE: entry()}))

    def expired(path):
        return real_load(tmp_path / "expired.json", today=date(2026, 11, 4))

    monkeypatch.setattr(audit, "load_exceptions", expired)
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: pytest.fail("Expired exception reached scanner"))
    assert audit.main() == 2
    assert "expired" in capsys.readouterr().err


def test_cli_success_only_for_reviewed_findings(monkeypatch, tmp_path):
    exceptions = load(tmp_path, {CVE: entry()})
    monkeypatch.setattr(audit, "load_exceptions", lambda path: exceptions)
    monkeypatch.setattr(audit.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, json.dumps(report()), ""))
    assert audit.main() == 0


@pytest.mark.parametrize("status", [0, 1])
def test_cli_rejects_zero_audited_dependencies(monkeypatch, capsys, status):
    monkeypatch.setattr(audit, "load_exceptions", lambda path: {})
    monkeypatch.setattr(
        audit.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], status, '{"dependencies":[]}', "")
    )
    assert audit.main() == 2
    assert "zero audited dependencies" in capsys.readouterr().err


@pytest.mark.parametrize("identity,aliases", [(CVE, ["CVE-2026-999999"]), ("GHSA-test", [CVE, "CVE-2026-999999"])])
def test_one_allowed_cve_cannot_hide_another_cve(tmp_path, capsys, identity, aliases):
    exceptions = load(tmp_path, {CVE: entry()})
    assert audit.report_findings(report(identity=identity, aliases=aliases), exceptions) == 1
    output = capsys.readouterr().out
    assert "UNRESOLVED" in output
    assert "CVE-2026-999999" in output


def test_every_cve_in_multi_cve_advisory_requires_a_scoped_exception(tmp_path):
    other_cve = "CVE-2026-112404"
    finding = report(identity="PYSEC-test", aliases=[CVE, other_cve, "GHSA-test"])
    assert audit.report_findings(finding, load(tmp_path, {CVE: entry(), other_cve: entry()})) == 0
    assert audit.report_findings(finding, load(tmp_path, {CVE: entry()})) == 1
    # Both identifiers are reviewed, but the second is not authorized for Pillow.
    assert audit.report_findings(report(aliases=["CVE-2025-54121"]), load(tmp_path, {CVE: entry()})) == 1


@pytest.mark.parametrize("identity,aliases", [("PYSEC-test", [CVE, "GHSA-test"]), ("GHSA-test", [CVE, CVE, "PYSEC-test"])])
def test_non_cve_aliases_and_duplicate_cves_remain_supported(tmp_path, identity, aliases):
    assert audit.report_findings(report(identity=identity, aliases=aliases), load(tmp_path, {CVE: entry()})) == 0
