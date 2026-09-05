from __future__ import annotations

import runpy
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine

from app.db import maintenance

ALEMBIC_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _create_legacy_schema(path: Path, *, with_member_en: bool, with_project_en: bool) -> None:
    revisions = ["8bb452b5f586"]
    if with_member_en:
        revisions.append("ce87631b7c22")
    if with_project_en:
        revisions.append("4b08cbb499e2")
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                for revision in revisions:
                    migration = next(ALEMBIC_VERSIONS_DIR.glob(f"{revision}_*.py"))
                    runpy.run_path(str(migration))["upgrade"]()
    finally:
        engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO member (name, role, email, display_order, created_at, updated_at) "
            "VALUES ('kept', 'master', 'kept@example.test', 100, '2026-01-01', '2026-01-01')"
        )


def _member_names(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return [row[0] for row in connection.execute("SELECT name FROM member ORDER BY id")]


def test_sqlite_path_from_url_handles_relative_absolute_and_other_engines(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    assert maintenance.sqlite_path_from_url("sqlite:///./nlp_lab.db") == tmp_path / "nlp_lab.db"
    assert maintenance.sqlite_path_from_url("sqlite:////srv/data/site.db") == Path(
        "/srv/data/site.db"
    )
    assert maintenance.sqlite_path_from_url("sqlite://") is None
    assert maintenance.sqlite_path_from_url("postgresql://user@host/db") is None


def test_backup_copies_data_and_prunes_old_backups(tmp_path: Path):
    db_path = tmp_path / "live.db"
    backup_dir = tmp_path / "backups"
    _create_legacy_schema(db_path, with_member_en=True, with_project_en=True)

    created = [
        maintenance.backup_database(
            db_path, backup_dir, keep=2, now=datetime(2026, 8, 25, 12, 0, index)
        )
        for index in range(3)
    ]

    remaining = sorted(backup_dir.glob("nlp_lab-*.db"))
    assert remaining == created[1:]
    assert _member_names(remaining[-1]) == ["kept"]


def test_backup_is_consistent_while_database_is_in_wal_mode(tmp_path: Path):
    db_path = tmp_path / "live.db"
    _create_legacy_schema(db_path, with_member_en=True, with_project_en=True)
    writer = sqlite3.connect(db_path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("UPDATE member SET name = 'in-wal'")
    writer.commit()

    try:
        backup_path = maintenance.backup_database(db_path, tmp_path / "backups")
    finally:
        writer.close()

    assert _member_names(backup_path) == ["in-wal"]


def test_restore_replaces_database_and_keeps_safety_copy(tmp_path: Path):
    db_path = tmp_path / "live.db"
    backup_dir = tmp_path / "backups"
    _create_legacy_schema(db_path, with_member_en=True, with_project_en=True)
    backup_path = maintenance.backup_database(db_path, backup_dir)
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE member SET name = 'after-backup'")
    db_path.with_name("live.db-wal").write_bytes(b"stale")

    safety_copy = maintenance.restore_database(backup_path, db_path, backup_dir)

    assert _member_names(db_path) == ["kept"]
    assert safety_copy is not None and safety_copy.name.startswith("pre-rollback-")
    assert _member_names(safety_copy) == ["after-backup"]
    assert not db_path.with_name("live.db-wal").exists()


def test_legacy_stamp_revision_detects_schema_generation(tmp_path: Path):
    latest = tmp_path / "latest.db"
    _create_legacy_schema(latest, with_member_en=True, with_project_en=True)
    assert maintenance.legacy_stamp_revision(latest) == "4b08cbb499e2"

    member_only = tmp_path / "member_only.db"
    _create_legacy_schema(member_only, with_member_en=True, with_project_en=False)
    assert maintenance.legacy_stamp_revision(member_only) == "ce87631b7c22"

    initial = tmp_path / "initial.db"
    _create_legacy_schema(initial, with_member_en=False, with_project_en=False)
    assert maintenance.legacy_stamp_revision(initial) == "8bb452b5f586"


def test_legacy_stamp_revision_is_none_for_tracked_or_empty_databases(tmp_path: Path):
    tracked = tmp_path / "tracked.db"
    _create_legacy_schema(tracked, with_member_en=True, with_project_en=True)
    with sqlite3.connect(tracked) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
        connection.execute("INSERT INTO alembic_version VALUES ('4b08cbb499e2')")
    assert maintenance.legacy_stamp_revision(tracked) is None

    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert maintenance.legacy_stamp_revision(empty) is None
    assert maintenance.legacy_stamp_revision(tmp_path / "missing.db") is None


def test_legacy_stamp_revision_refuses_unknown_schema(tmp_path: Path):
    partial = tmp_path / "partial.db"
    with sqlite3.connect(partial) as connection:
        connection.execute("CREATE TABLE member (id INTEGER PRIMARY KEY)")

    with pytest.raises(maintenance.SchemaNotRecognisedError):
        maintenance.legacy_stamp_revision(partial)


def test_legacy_revisions_exist_in_alembic_history():
    revision_files = {path.name.split("_", 1)[0] for path in ALEMBIC_VERSIONS_DIR.glob("*.py")}
    for revision in maintenance.LEGACY_SCHEMA_REVISIONS:
        assert revision in revision_files


def test_cli_backup_and_stamp_commands(tmp_path: Path, capsys):
    db_path = tmp_path / "live.db"
    _create_legacy_schema(db_path, with_member_en=True, with_project_en=False)
    url = f"sqlite:///{db_path}"
    backup_dir = tmp_path / "backups"

    assert maintenance.main(["--database-url", url, "--backup-dir", str(backup_dir), "backup"]) == 0
    backup_path = Path(capsys.readouterr().out.strip())
    assert backup_path.parent == backup_dir and backup_path.exists()

    assert maintenance.main(["--database-url", url, "legacy-stamp-revision"]) == 0
    assert capsys.readouterr().out.strip() == "ce87631b7c22"

    assert maintenance.main(["--database-url", "postgresql://u@h/db", "backup"]) == 0
    assert capsys.readouterr().out == ""

    broken = tmp_path / "broken.db"
    with sqlite3.connect(broken) as connection:
        connection.execute("CREATE TABLE post (id INTEGER PRIMARY KEY)")
    assert maintenance.main(["--database-url", f"sqlite:///{broken}", "legacy-stamp-revision"]) == 2


def test_legacy_refuses_matching_table_names_with_unrelated_columns(tmp_path):
    path = tmp_path / "unknown.db"
    with sqlite3.connect(path) as connection:
        for table in ("admin_user", "member", "project", "publication", "post"):
            connection.execute(f"CREATE TABLE {table} (unrelated TEXT)")
    with pytest.raises(maintenance.SchemaNotRecognisedError):
        maintenance.legacy_stamp_revision(path)


@pytest.mark.parametrize(
    "alteration",
    [
        "ALTER TABLE member ADD COLUMN name_en VARCHAR(100)",
        "DROP INDEX ix_publication_year",
        "ALTER TABLE post DROP COLUMN content",
        "CREATE TABLE unrelated (id INTEGER PRIMARY KEY)",
    ],
)
def test_legacy_refuses_partial_or_modified_generations(tmp_path, alteration):
    path = tmp_path / "partial.db"
    _create_legacy_schema(path, with_member_en=False, with_project_en=False)
    with sqlite3.connect(path) as connection:
        connection.execute(alteration)
    with pytest.raises(maintenance.SchemaNotRecognisedError):
        maintenance.legacy_stamp_revision(path)


def test_empty_alembic_table_does_not_hide_existing_schema(tmp_path):
    path = tmp_path / "empty-version.db"
    _create_legacy_schema(path, with_member_en=True, with_project_en=False)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
    assert maintenance.legacy_stamp_revision(path) == "ce87631b7c22"
