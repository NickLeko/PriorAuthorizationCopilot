"""Audit the deployment lock; only documented CVE exceptions are allowed."""

import json
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    exceptions = json.loads((root / "security/pip-audit-ignores.json").read_text())
    command = [sys.executable, "-m", "pip_audit", "-r", str(root / "requirements.lock"), "--disable-pip", "--strict"]
    for cve, entry in sorted(exceptions.items()):
        if not cve.startswith("CVE-") or entry["package"] != "starlette" or not entry["reason"].strip():
            raise ValueError("Every exception requires a Starlette CVE and an unreachability reason.")
        command.extend(["--ignore-vuln", cve])
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
