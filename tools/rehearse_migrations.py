"""Back up and migrate a temporary SQLite copy, verifying pre-existing domain values."""

import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("database", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="soundbridge-migration-check-") as directory:
    copy = Path(directory) / "copy.sqlite3"
    with (
        sqlite3.connect(
            "file:" + str(args.database.resolve()) + "?mode=ro", uri=True
        ) as source,
        sqlite3.connect(copy) as target,
    ):
        source.backup(target)
        tables = [
            row[0]
            for row in target.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if row[0].startswith(
                ("accounts_", "network_", "releases_", "royalties_", "aiteam_")
            )
        ]
        columns = {
            name: [row[1] for row in target.execute(f'PRAGMA table_info("{name}")')]
            for name in tables
        }

        def digest(connection, table):
            selected = ",".join('"' + column + '"' for column in columns[table])
            rows = sorted(
                repr(row)
                for row in connection.execute(f'SELECT {selected} FROM "{table}"')
            )
            return len(rows), hashlib.sha256("\n".join(rows).encode()).hexdigest()

        before = {name: digest(target, name) for name in tables}
    env = {
        **os.environ,
        "SOUNDBRIDGE_DJANGO_DATABASE": str(copy),
        "POSTGRES_DB": "",
        "SOUNDBRIDGE_PUBLIC_ORIGIN": "",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    with sqlite3.connect(copy) as target:
        after = {name: digest(target, name) for name in tables}
    assert before == after, "Pre-existing domain values changed unexpectedly."
    print(
        f"Migration rehearsal passed: counts and values preserved across {len(tables)} existing domain tables. Original database unchanged."
    )
