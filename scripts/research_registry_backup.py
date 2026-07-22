#!/usr/bin/env python3
"""Cross-platform, fail-closed backup and restore drills for the research registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "research-registry-backup-manifest-v1"
POLICY_SCHEMA = "research-registry-backup-policy-v1"


class RegistryBackupError(RuntimeError):
    """Raised when a backup operation cannot prove that it is safe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryBackupError(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RegistryBackupError(f"JSON document must be an object: {path}")
    return value


def load_policy(path: Path) -> dict[str, Any]:
    policy = _read_json(path)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise RegistryBackupError("backup policy schema_version is invalid")
    expected = policy.get("policy_fingerprint")
    unsigned = {key: value for key, value in policy.items() if key != "policy_fingerprint"}
    if expected != _fingerprint(unsigned):
        raise RegistryBackupError("backup policy fingerprint mismatch")
    retention = policy.get("retention")
    if not isinstance(retention, dict):
        raise RegistryBackupError("backup policy retention is invalid")
    if type(retention.get("keep_last")) is not int or retention["keep_last"] < 1:
        raise RegistryBackupError("backup policy keep_last is invalid")
    if type(retention.get("maximum_age_days")) is not int or retention["maximum_age_days"] < 1:
        raise RegistryBackupError("backup policy maximum_age_days is invalid")
    return policy


def _readonly_connection(path: Path) -> sqlite3.Connection:
    if not path.exists() or not path.is_file():
        raise RegistryBackupError(f"registry source does not exist: {path}")
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection
    except sqlite3.Error as exc:
        raise RegistryBackupError(f"cannot open registry read-only: {path}") from exc


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def inspect_registry(path: Path) -> dict[str, Any]:
    connection = _readonly_connection(path)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        integrity_check = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        if quick_check != "ok" or integrity_check != "ok" or foreign_key_violations:
            raise RegistryBackupError(f"SQLite integrity check failed: {path}")
        tables = sorted(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        if "director_schema_migrations" not in tables:
            raise RegistryBackupError("director_schema_migrations table is missing")
        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
            ).fetchone()[0]
            for table in tables
        }
        schema_version = connection.execute(
            "SELECT MAX(version) FROM director_schema_migrations"
        ).fetchone()[0]
        if type(schema_version) is not int or schema_version < 1:
            raise RegistryBackupError("director schema version is invalid")
        return {
            "quick_check": quick_check,
            "integrity_check": integrity_check,
            "foreign_key_violations": foreign_key_violations,
            "director_schema_version": schema_version,
            "table_counts": counts,
        }
    except sqlite3.Error as exc:
        raise RegistryBackupError(f"cannot inspect SQLite registry: {path}") from exc
    finally:
        connection.close()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_backup(source: Path, backup_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    source = source.resolve()
    if not source.exists() or not source.is_file():
        raise RegistryBackupError(f"registry source does not exist: {source}")
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = (now or _utc_now()).astimezone(timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    temporary = backup_root / f".registry-backup-{uuid.uuid4().hex}.tmp"
    final: Path | None = None
    manifest_path: Path | None = None
    source_connection = _readonly_connection(source)
    try:
        source_quick = source_connection.execute("PRAGMA quick_check").fetchone()[0]
        source_integrity = source_connection.execute("PRAGMA integrity_check").fetchone()[0]
        if source_quick != "ok" or source_integrity != "ok":
            raise RegistryBackupError("source registry integrity check failed")
        destination = sqlite3.connect(temporary)
        try:
            source_connection.backup(destination)
            destination.commit()
        finally:
            destination.close()
    except sqlite3.Error as exc:
        raise RegistryBackupError("SQLite online backup failed") from exc
    finally:
        source_connection.close()

    try:
        snapshot = inspect_registry(temporary)
        digest = _sha256(temporary)
        backup_id = f"registry-backup-{stamp}-{digest[:12]}"
        final = backup_root / f"{backup_id}.sqlite"
        manifest_path = backup_root / f"{backup_id}.manifest.json"
        if final.exists() or manifest_path.exists():
            raise RegistryBackupError(f"backup identifier collision: {backup_id}")
        os.replace(temporary, final)
        manifest: dict[str, Any] = {
            "schema_version": MANIFEST_SCHEMA,
            "backup_id": backup_id,
            "created_at": _iso(timestamp),
            "backup_file": final.name,
            "backup_bytes": final.stat().st_size,
            "backup_sha256": digest,
            "source": {
                "path": str(source),
                "opened_read_only": True,
                "method": "sqlite_backup_api",
                "source_file_hash_equivalence_claimed": False,
            },
            "snapshot": snapshot,
            "restore_constraints": {
                "live_overwrite_allowed": False,
                "restore_target_must_not_exist": True,
            },
        }
        manifest["manifest_fingerprint"] = _fingerprint(manifest)
        _atomic_json(manifest_path, manifest)
        return {**manifest, "manifest_path": str(manifest_path.resolve())}
    except Exception:
        if manifest_path is not None:
            manifest_path.unlink(missing_ok=True)
        if final is not None:
            final.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise RegistryBackupError("backup manifest schema_version is invalid")
    expected_fingerprint = manifest.get("manifest_fingerprint")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
    if expected_fingerprint != _fingerprint(unsigned):
        raise RegistryBackupError("backup manifest fingerprint mismatch")
    backup_file = manifest.get("backup_file")
    if not isinstance(backup_file, str) or Path(backup_file).name != backup_file:
        raise RegistryBackupError("backup_file must be a plain filename")
    backup_path = manifest_path.parent / backup_file
    if not backup_path.exists() or not backup_path.is_file():
        raise RegistryBackupError("backup file is missing")
    if backup_path.stat().st_size != manifest.get("backup_bytes"):
        raise RegistryBackupError("backup file size mismatch")
    if _sha256(backup_path) != manifest.get("backup_sha256"):
        raise RegistryBackupError("backup SHA256 mismatch")
    snapshot = inspect_registry(backup_path)
    if snapshot != manifest.get("snapshot"):
        raise RegistryBackupError("backup logical snapshot mismatch")
    return {
        "status": "verified",
        "backup_id": manifest["backup_id"],
        "manifest_path": str(manifest_path),
        "backup_path": str(backup_path.resolve()),
        "backup_sha256": manifest["backup_sha256"],
        "snapshot": snapshot,
    }


def restore_drill(manifest_path: Path, target: Path) -> dict[str, Any]:
    verified = verify_manifest(manifest_path)
    target = target.resolve()
    if target.exists():
        raise RegistryBackupError(f"restore target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copyfile(Path(verified["backup_path"]), temporary)
        if _sha256(temporary) != verified["backup_sha256"]:
            raise RegistryBackupError("restored file SHA256 mismatch")
        if inspect_registry(temporary) != verified["snapshot"]:
            raise RegistryBackupError("restored logical snapshot mismatch")
        os.replace(temporary, target)
        return {
            "status": "restore_drill_passed",
            "backup_id": verified["backup_id"],
            "target": str(target),
            "target_sha256": _sha256(target),
            "live_registry_overwritten": False,
        }
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def prune_backups(
    backup_root: Path,
    *,
    keep_last: int,
    maximum_age_days: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or _utc_now()).astimezone(timezone.utc)
    manifests: list[tuple[datetime, Path, dict[str, Any]]] = []
    for path in backup_root.glob("registry-backup-*.manifest.json"):
        payload = _read_json(path)
        try:
            created = datetime.fromisoformat(str(payload["created_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryBackupError(f"backup manifest created_at is invalid: {path}") from exc
        manifests.append((created.astimezone(timezone.utc), path, payload))
    manifests.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    cutoff_seconds = maximum_age_days * 86400
    candidates = [
        item
        for index, item in enumerate(manifests)
        if index >= keep_last and (current - item[0]).total_seconds() > cutoff_seconds
    ]
    verified_candidates: list[tuple[Path, Path, str]] = []
    for _, manifest_path, payload in candidates:
        verified = verify_manifest(manifest_path)
        verified_candidates.append(
            (manifest_path, Path(verified["backup_path"]), str(payload["backup_id"]))
        )
    for manifest_path, backup_path, _ in verified_candidates:
        backup_path.unlink()
        manifest_path.unlink()
    return {
        "status": "pruned",
        "kept": len(manifests) - len(verified_candidates),
        "deleted_backup_ids": [item[2] for item in verified_candidates],
        "unknown_files_deleted": False,
    }


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--policy",
        default="research/governance/research-registry-backup-policy-v1.json",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup = subparsers.add_parser("backup")
    backup.add_argument("--source")
    backup.add_argument("--backup-root")
    backup.add_argument("--prune", action="store_true")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    restore = subparsers.add_parser("restore-drill")
    restore.add_argument("--manifest", type=Path, required=True)
    restore.add_argument("--target", type=Path, required=True)
    prune = subparsers.add_parser("prune")
    prune.add_argument("--backup-root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repo_root = args.repo_root.resolve()
        policy = load_policy(_resolve(repo_root, args.policy))
        if args.command == "backup":
            source = _resolve(repo_root, args.source or policy["default_source"])
            backup_root = _resolve(repo_root, args.backup_root or policy["default_backup_root"])
            result = create_backup(source, backup_root)
            if args.prune:
                result["retention"] = prune_backups(backup_root, **policy["retention"])
        elif args.command == "verify":
            result = verify_manifest(args.manifest)
        elif args.command == "restore-drill":
            result = restore_drill(args.manifest, args.target)
        else:
            backup_root = _resolve(repo_root, args.backup_root or policy["default_backup_root"])
            result = prune_backups(backup_root, **policy["retention"])
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (RegistryBackupError, OSError, KeyError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
