"""Small append-only SQLite archive. Hashes detect corruption, not a privileged attacker."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .policies import canonical_json, content_hash
from .schemas import EvaluationResult, PolicyVersion


class DecisionStore:
    def __init__(self, path: str | Path, *, readonly: bool = False):
        path = Path(path).resolve()
        if not readonly:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(f"{path.as_uri()}?mode={'ro' if readonly else 'rwc'}", uri=True)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA recursive_triggers = ON")
        if not readonly:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT NOT NULL, version_id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (policy_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, version_id TEXT NOT NULL,
                    payload TEXT NOT NULL, content_hash TEXT NOT NULL,
                    FOREIGN KEY (policy_id, version_id) REFERENCES policies(policy_id, version_id)
                );
            """)
            for table, key in (
                ("policies", "policy_id = NEW.policy_id AND version_id = NEW.version_id"),
                ("decisions", "decision_id = NEW.decision_id"),
            ):
                for operation in ("UPDATE", "DELETE"):
                    self.connection.execute(f"""
                        CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()}
                        BEFORE {operation} ON {table}
                        BEGIN SELECT RAISE(ABORT, 'Archive records are immutable'); END
                    """)
                self.connection.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table}
                    WHEN EXISTS (SELECT 1 FROM {table} WHERE {key})
                    BEGIN SELECT RAISE(ABORT, 'Archive identity already exists'); END
                """)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.connection.close()

    def add_policy(self, policy: PolicyVersion) -> None:
        policy = PolicyVersion.model_validate_json(policy.model_dump_json())
        payload = canonical_json(policy.model_dump(mode="json"))
        existing = self.connection.execute(
            "SELECT payload FROM policies WHERE policy_id = ? AND version_id = ?", (policy.policy_id, policy.version_id)
        ).fetchone()
        if existing:
            if existing[0] != payload:
                raise ValueError("Policy version identity already exists with different content.")
            return
        with self.connection:
            self.connection.execute("INSERT INTO policies VALUES (?, ?, ?)", (policy.policy_id, policy.version_id, payload))

    def get_policy(self, policy_id: str, version_id: str) -> PolicyVersion:
        row = self.connection.execute(
            "SELECT payload FROM policies WHERE policy_id = ? AND version_id = ?", (policy_id, version_id)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown policy version: {policy_id}/{version_id}")
        policy = PolicyVersion.model_validate_json(row[0])
        if (policy.policy_id, policy.version_id) != (policy_id, version_id):
            raise ValueError("Stored policy identity mismatch.")
        return policy

    def list_policies(self) -> list[dict]:
        rows = self.connection.execute("SELECT policy_id, version_id FROM policies ORDER BY policy_id, version_id").fetchall()
        return [self.get_policy(*row).model_dump(mode="json") for row in rows]

    def record(self, evaluation: EvaluationResult, decision_id: str | None = None) -> str:
        evaluation = EvaluationResult.model_validate_json(evaluation.model_dump_json())
        policy = evaluation.policy_version
        if policy != evaluation.audit_trail.policy_version:
            raise ValueError("Decision and audit policy versions disagree.")
        if (policy.payer, policy.procedure_code) != (evaluation.request.payer, evaluation.request.procedure_code):
            raise ValueError("Decision and policy scope disagree.")
        self.add_policy(policy)
        decision_id = decision_id or evaluation.audit_trail.run_id
        if not decision_id.strip():
            raise ValueError("Decision ID must be non-empty.")
        payload = evaluation.model_dump(mode="json")
        with self.connection:
            self.connection.execute(
                "INSERT INTO decisions VALUES (?, ?, ?, ?, ?)",
                (
                    decision_id,
                    policy.policy_id,
                    policy.version_id,
                    canonical_json(payload),
                    content_hash({"decision_id": decision_id, "evaluation": payload}),
                ),
            )
        return decision_id

    def get_decision(self, decision_id: str) -> EvaluationResult:
        row = self.connection.execute(
            "SELECT payload, content_hash, policy_id, version_id FROM decisions WHERE decision_id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown historical decision: {decision_id}")
        result = EvaluationResult.model_validate_json(row[0])
        if content_hash({"decision_id": decision_id, "evaluation": result.model_dump(mode="json")}) != row[1]:
            raise ValueError(f"Decision content hash mismatch: {decision_id}")
        if result.policy_version != self.get_policy(row[2], row[3]) or result.policy_version != result.audit_trail.policy_version:
            raise ValueError("Stored decision policy mismatch.")
        return result

    def decision_ids(self, policy_id: str | None = None, version_id: str | None = None) -> list[str]:
        rows = self.connection.execute(
            "SELECT decision_id FROM decisions WHERE (? IS NULL OR policy_id = ?) AND (? IS NULL OR version_id = ?) ORDER BY decision_id",
            (policy_id, policy_id, version_id, version_id),
        )
        return [row[0] for row in rows]
