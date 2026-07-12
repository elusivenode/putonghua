"""Ordered SQLite migration support."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from putonghua.database.connection import connect

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@dataclass(frozen=True)
class Migration:
    """A single SQL migration file."""

    version: str
    path: Path


def discover_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Return ordered migration definitions from disk."""

    migrations = [
        Migration(version=path.stem, path=path)
        for path in sorted(migrations_dir.glob("*.sql"))
    ]
    return migrations


def migrate_database(database_path: Path) -> list[str]:
    """Apply all pending migrations and return their versions."""

    with connect(database_path) as connection:
        _ensure_schema_migrations_table(connection)
        applied_versions = _load_applied_versions(connection)
        pending = [
            migration
            for migration in discover_migrations()
            if migration.version not in applied_versions
        ]

        for migration in pending:
            sql = migration.path.read_text(encoding="utf-8")
            with connection:
                connection.executescript(sql)
                connection.execute(
                    """
                    INSERT INTO schema_migrations(version)
                    VALUES (?)
                    """,
                    (migration.version,),
                )

        return [migration.version for migration in pending]


def _ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
    """Create the migration bookkeeping table if needed."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _load_applied_versions(connection: sqlite3.Connection) -> set[str]:
    """Fetch already-applied migration versions."""

    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    return {str(row["version"]) for row in rows}
