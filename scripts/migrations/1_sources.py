"""
Migration script to add 'sources' and 'source_word' tables to an existing SQLite DB.

Usage:
  python migrate_add_sources.py
"""

import sqlite3
import os

# Adjust this path if your DB file is elsewhere or dynamically loaded.
DATABASE_FILE = "wordlist.db"


def migrate_add_sources_and_source_word(db_path: str):
    """
    Adds two new tables:
      (1) 'sources': holds the location and identification of a source
      (2) 'source_word': relationship table between 'sources' and 'wordlist' entries
    """
    conn = sqlite3.connect(db_path)
    try:
        # Create 'sources' table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                name   TEXT NOT NULL UNIQUE CHECK(LENGTH(name) <= 50),
                source TEXT NOT NULL UNIQUE CHECK(LENGTH(source) <= 50),
                file   TEXT NOT NULL UNIQUE CHECK(LENGTH(file) <= 50)
            );
            """
        )

        # Create 'source_word' table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_word (
                source_id INTEGER NOT NULL,
                word_id   TEXT NOT NULL,
                score     INTEGER,
                FOREIGN KEY(source_id) REFERENCES sources(id)
                  ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY(word_id) REFERENCES wordlist(answers)
                  ON UPDATE CASCADE ON DELETE CASCADE,
                PRIMARY KEY (source_id, word_id)
            );
            """
        )

        conn.commit()
        print("Migration complete: 'sources' and 'source_word' tables added.")
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


def main():
    if not os.path.exists(DATABASE_FILE):
        print(f"Database file not found at '{DATABASE_FILE}'. Create it first.")
        return
    migrate_add_sources_and_source_word(DATABASE_FILE)


if __name__ == "__main__":
    main()
