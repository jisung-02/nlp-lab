"""Operational helpers used by ``scripts/deploy.sh`` and ``scripts/rollback.sh``.

Backup and restore use SQLite directly. Legacy schema checks compare against
the Alembic migrations without importing application models.

Commands (``python -m app.db.maintenance <command>``):

- ``backup``: copy the live database into ``backups/`` using SQLite's
  online backup API (consistent even while the app is running in WAL
  mode) and prune old copies. Prints the backup path.
- ``restore <path>``: replace the live database with a backup. The
  current database is saved to ``backups/`` first.
- ``legacy-stamp-revision``: for databases created before Alembic was
  introduced (no ``alembic_version`` table), print the migration
  revision that matches the existing schema so the deploy script can
  ``alembic stamp`` it before running ``alembic upgrade head``. Prints
  nothing when no stamping is needed; exits with status 2 when the
  schema is not recognised so nobody guesses on production data.
"""

from __future__ import annotations

import argparse
import runpy
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import cast

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups"
DEFAULT_BACKUP_KEEP = 10

# Old schemas without an Alembic version must match a complete known generation.
LEGACY_SCHEMA_REVISIONS = ("8bb452b5f586", "ce87631b7c22", "4b08cbb499e2")


class SchemaNotRecognisedError(RuntimeError):
    """Raised when an existing database doesn't match any known revision."""


def sqlite_path_from_url(database_url: str) -> Path | None:
    """Return the on-disk path for a SQLite URL, or ``None`` for other engines."""

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    database = url.database
    if not database or database == ":memory:":
        return None
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def backup_database(
    database_path: Path,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    *,
    keep: int = DEFAULT_BACKUP_KEEP,
    label: str = "nlp_lab",
    now: datetime | None = None,
) -> Path:
    """Copy ``database_path`` into ``backup_dir`` and prune old backups."""

    if not database_path.exists():
        raise FileNotFoundError(f"database file not found: {database_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{label}-{timestamp}.db"
    counter = 1
    while backup_path.exists():
        backup_path = backup_dir / f"{label}-{timestamp}-{counter}.db"
        counter += 1

    _copy_sqlite(database_path, backup_path)
    _prune_backups(backup_dir, label=label, keep=keep)
    return backup_path


def restore_database(
    backup_path: Path,
    database_path: Path,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
) -> Path | None:
    """Replace ``database_path`` with ``backup_path``.

    The current database (if any) is copied into ``backup_dir`` first so a
    rollback can itself be undone. Returns that safety copy's path.
    """

    if not backup_path.exists():
        raise FileNotFoundError(f"backup file not found: {backup_path}")

    safety_copy: Path | None = None
    if database_path.exists():
        safety_copy = backup_database(
            database_path, backup_dir, keep=DEFAULT_BACKUP_KEEP, label="pre-rollback"
        )

    database_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        stale = database_path.with_name(database_path.name + suffix)
        if stale.exists():
            stale.unlink()
    _copy_sqlite(backup_path, database_path)
    return safety_copy


def legacy_stamp_revision(database_path: Path) -> str | None:
    """Return the revision to ``alembic stamp`` for an untracked database.

    ``None`` means Alembic already tracks this database (or it is empty),
    so ``alembic upgrade head`` can run as-is.
    """

    if not database_path.exists():
        return None

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if "alembic_version" in tables:
            if connection.execute("SELECT version_num FROM alembic_version").fetchone():
                return None
        actual_schema = _schema_signature(connection)
        if not actual_schema:
            return None

    reference_engine = create_engine("sqlite://")
    try:
        with reference_engine.begin() as reference:
            with Operations.context(MigrationContext.configure(reference)):
                for revision in LEGACY_SCHEMA_REVISIONS:
                    migration = next(
                        (PROJECT_ROOT / "alembic" / "versions").glob(f"{revision}_*.py")
                    )
                    runpy.run_path(str(migration))["upgrade"]()
                    if (
                        _schema_signature(
                            cast(sqlite3.Connection, reference.connection.driver_connection)
                        )
                        == actual_schema
                    ):
                        return revision
    finally:
        reference_engine.dispose()
    raise SchemaNotRecognisedError("columns, keys or indexes do not match a known legacy schema")


def _schema_signature(connection: sqlite3.Connection) -> dict:
    """Compare column definitions, primary/unique keys, foreign keys and indexes."""
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )
    ]
    schema = {}
    for table in tables:
        quoted = table.replace('"', '""')
        columns = tuple(
            sorted(tuple(row[1:]) for row in connection.execute(f'PRAGMA table_info("{quoted}")'))
        )
        foreign_keys = tuple(
            sorted(
                tuple(row[2:]) for row in connection.execute(f'PRAGMA foreign_key_list("{quoted}")')
            )
        )
        indexes = []
        for row in connection.execute(f'PRAGMA index_list("{quoted}")'):
            index = row[1].replace('"', '""')
            fields = tuple(item[2] for item in connection.execute(f'PRAGMA index_info("{index}")'))
            indexes.append((row[2], row[4], fields))
        schema[table] = (columns, foreign_keys, tuple(sorted(indexes, key=repr)))
    return schema


def _copy_sqlite(source: Path, destination: Path) -> None:
    source_connection = sqlite3.connect(source)
    try:
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
    finally:
        source_connection.close()


def _prune_backups(backup_dir: Path, *, label: str, keep: int) -> None:
    backups = sorted(backup_dir.glob(f"{label}-*.db"))
    for stale in backups[:-keep] if keep > 0 else backups:
        stale.unlink()


def _resolve_database_path(database_url: str | None) -> Path | None:
    if database_url is None:
        from app.core.config import get_settings

        database_url = get_settings().database_url
    return sqlite_path_from_url(database_url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.db.maintenance")
    parser.add_argument("--database-url", help="override DATABASE_URL from settings")
    parser.add_argument(
        "--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR, help="where backups are stored"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--keep", type=int, default=DEFAULT_BACKUP_KEEP)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup_path", type=Path)

    subparsers.add_parser("legacy-stamp-revision")

    args = parser.parse_args(argv)
    database_path = _resolve_database_path(args.database_url)

    if args.command == "backup":
        if database_path is None:
            print("not a file-based SQLite database; skipping backup", file=sys.stderr)
            return 0
        if not database_path.exists():
            print(f"no database yet at {database_path}; nothing to back up", file=sys.stderr)
            return 0
        print(backup_database(database_path, args.backup_dir, keep=args.keep))
        return 0

    if args.command == "restore":
        if database_path is None:
            print("not a file-based SQLite database; cannot restore", file=sys.stderr)
            return 1
        safety_copy = restore_database(args.backup_path, database_path, args.backup_dir)
        if safety_copy is not None:
            print(f"previous database kept at {safety_copy}", file=sys.stderr)
        print(database_path)
        return 0

    if args.command == "legacy-stamp-revision":
        if database_path is None:
            return 0
        try:
            revision = legacy_stamp_revision(database_path)
        except SchemaNotRecognisedError as error:
            print(f"database schema not recognised: {error}", file=sys.stderr)
            return 2
        if revision is not None:
            print(revision)
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
