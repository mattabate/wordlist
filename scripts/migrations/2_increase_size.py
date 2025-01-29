#!/usr/bin/env python3
"""
Migration script to allow up to 200 characters in the 'sources' table columns:
  - name
  - source
  - file

Usage:
  python migrate_increase_length.py
"""

import sqlite3
import os
import yaml

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    DATABASE_FILE = config["db_file"]


def migrate_sources_len_200(db_path: str):
    """
    Replaces the old 'sources' table (with LENGTH <= 50)
    with a new 'sources' table (with LENGTH <= 200).
    Preserves existing rows.
    """

    if not os.path.exists(db_path):
        print(f"Database file '{db_path}' does not exist.")
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # 1. Rename old table to a temporary name
        cursor.execute("ALTER TABLE sources RENAME TO sources_old;")

        # 2. Create new table with updated constraints
        cursor.execute(
            """
            CREATE TABLE sources (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                name   TEXT NOT NULL UNIQUE CHECK(LENGTH(name) <= 200),
                source TEXT NOT NULL UNIQUE CHECK(LENGTH(source) <= 200),
                file   TEXT NOT NULL UNIQUE CHECK(LENGTH(file) <= 200)
            );
            """
        )

        # 3. Copy data from old table to new one
        #    (Assumes columns are named the same)
        cursor.execute(
            """
            INSERT INTO sources (id, name, source, file)
            SELECT id, name, source, file
            FROM sources_old;
            """
        )

        # 4. Drop the old table
        cursor.execute("DROP TABLE sources_old;")

        # 5. Commit changes
        conn.commit()

        print(
            "Migration complete: updated 'sources' to allow up to 200 chars in name/source/file."
        )

    except sqlite3.Error as e:
        # Roll back if something goes wrong
        print(f"SQLite error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_sources_len_200(DATABASE_FILE)
