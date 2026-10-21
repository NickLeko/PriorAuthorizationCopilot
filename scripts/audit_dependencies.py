"""Audit the deployment lock; only documented CVE exceptions are allowed."""

import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# These are the only reviewed exceptions. New advisories require code review.
STARLETTE_CVES = frozenset(
    {
        "CVE-2025-54121",
        "CVE-2025-62727",
        "CVE-2026-48710",
        "CVE-2026-48817",
        "CVE-2026-48818",
        "CVE-2026-54282",
        "CVE-2026-54283",
    }
)
PILLOW_CVES = frozenset(
    {
        "CVE-2026-112895",
        "CVE-2026-112400",
        "CVE-2026-112397",
        "CVE-2026-112896",
        "CVE-2026-112897",
        "CVE-2026-112395",
        "CVE-2026-112404",
        "CVE-2026-112899",
    }
)
PILLOW_EXPIRY_LIMIT = date(2026, 11, 4)
PILLOW_REVIEWED_VERSION = "12.3.0"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_exceptions(path, *, today=None):
    today = today if today is not None else datetime.now(timezone.utc).date()
    exceptions = json.loads(path.read_text(), object_pairs_hook=unique_object)
    if not isinstance(exceptions, dict):
        raise ValueError("Exceptions must be a JSON object.")
    for cve, entry in exceptions.items():
        if cve in STARLETTE_CVES:
            package, fields = "starlette", {"package", "reason"}
        elif cve in PILLOW_CVES:
            package, fields = "pillow", {"package", "reason", "expires"}
        else:
            raise ValueError(f"Unrecognized exception: {cve}")
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError(f"{cve}: required fields are {sorted(fields)}.")
        if entry["package"] != package or not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise ValueError(f"{cve}: requires package {package!r} and a nonempty justification.")
        if package == "pillow":
            expiry_text = entry["expires"]
            if not isinstance(expiry_text, str):
                raise ValueError(f"{cve}: expires must be YYYY-MM-DD.")
            expiry = date.fromisoformat(expiry_text)
            if expiry.isoformat() != expiry_text or expiry > PILLOW_EXPIRY_LIMIT:
                raise ValueError(f"{cve}: expires must be YYYY-MM-DD, no later than {PILLOW_EXPIRY_LIMIT}.")
            # Expiration is the start of this date in UTC, including on clean scans.
            if today >= expiry:
                raise ValueError(f"{cve}: exception expired on {expiry} (UTC date: {today}).")
    return exceptions


def report_findings(report, exceptions):
    """Match CVE aliases only within their reviewed package (and Pillow version)."""
    if not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
        raise ValueError("Malformed pip-audit report: missing dependencies.")
    if not report["dependencies"]:
        raise ValueError("pip-audit returned zero audited dependencies.")
    findings = []
    # Validate the whole report before applying any exceptions.
    for dependency in report["dependencies"]:
        if not isinstance(dependency, dict) or not all(isinstance(dependency.get(k), str) for k in ("name", "version")):
            raise ValueError("Malformed or skipped pip-audit dependency.")
        if "skip_reason" in dependency or not isinstance(dependency.get("vulns"), list):
            raise ValueError("Malformed or skipped pip-audit dependency.")
        for vuln in dependency["vulns"]:
            if (
                not isinstance(vuln, dict)
                or not isinstance(vuln.get("id"), str)
                or not vuln["id"]
                or not isinstance(vuln.get("aliases", []), list)
                or not all(isinstance(alias, str) for alias in vuln.get("aliases", []))
                or not isinstance(vuln.get("fix_versions"), list)
                or not all(isinstance(version, str) for version in vuln["fix_versions"])
            ):
                raise ValueError("Malformed pip-audit vulnerability.")
            findings.append((dependency, vuln))

    for cve, entry in sorted(exceptions.items()):
        expiry = entry.get("expires", "legacy Starlette exception; no expiry")
        print(f"ACTIVE EXCEPTION {entry['package']} {cve}; expires: {expiry}; reason: {entry['reason']}", flush=True)

    remaining = ignored = 0
    for dependency, vuln in findings:
        ids = {vuln["id"], *vuln.get("aliases", [])}
        cves = {identity for identity in ids if identity.upper().startswith("CVE-")}
        matches = [
            cve
            for cve in sorted(ids & exceptions.keys())
            if exceptions[cve]["package"] == dependency["name"].lower()
            and (exceptions[cve]["package"] != "pillow" or dependency["version"] == PILLOW_REVIEWED_VERSION)
        ]
        label = f"{dependency['name']}=={dependency['version']} {vuln['id']}"
        # A merged advisory may represent several CVEs; each needs authorization.
        unreviewed = cves - set(matches)
        if matches and not unreviewed:
            ignored += 1
            print(f"EXCEPTED {label} (reviewed as {', '.join(matches)})")
        else:
            remaining += 1
            print(f"UNRESOLVED {label}; fix versions: {', '.join(vuln['fix_versions']) or 'unknown'}")
            if unreviewed:
                print(f"  CVEs without a matching package/version exception: {', '.join(sorted(unreviewed))}")
    print(f"Audit: {len(report['dependencies'])} dependencies; {remaining} unresolved findings; {ignored} excepted findings.")
    return 1 if remaining else 0


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        exceptions = load_exceptions(root / "security/pip-audit-ignores.json")
        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(root / "requirements.lock"),
            "--disable-pip",
            "--strict",
            "--format",
            "json",
            "--progress-spinner",
            "off",
        ]
        audit = subprocess.run(command, capture_output=True, text=True, check=False)
        if audit.stderr:
            print(audit.stderr, end="", file=sys.stderr)
        if audit.returncode not in (0, 1):
            return audit.returncode or 2
        report = json.loads(audit.stdout, object_pairs_hook=unique_object)
        # Exit 1 without any findings is an operational failure, not a clean scan.
        result = report_findings(report, exceptions)
        if audit.returncode == 1 and not any(dependency["vulns"] for dependency in report["dependencies"]):
            raise ValueError("pip-audit failed without a vulnerability report.")
        return result
    except (OSError, ValueError) as exc:
        print(f"Dependency audit failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
