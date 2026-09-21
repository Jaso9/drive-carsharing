"""SQLite backup/verification, without stopping the application or copying a live file."""

import argparse
import sqlite3
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import settings


def backup_sqlite(database_url: str, destination: Path):
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("Backup command requires a file-backed SQLite database")
    source = Path(url.database).resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise ValueError("Source database does not exist")
    if source == destination or destination.exists():
        raise ValueError("Destination must be a new file; existing files are never overwritten")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids accidentally overwriting an existing backup.
    with destination.open("xb"):
        pass
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed")
            if dst.execute("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Backup contains broken foreign keys")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New backup .db file")
    args = parser.parse_args()
    print(backup_sqlite(settings.database_url, args.destination))


if __name__ == "__main__":
    main()
