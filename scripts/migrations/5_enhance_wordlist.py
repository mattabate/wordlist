#!/usr/bin/env python3
"""
Migration script to:
1. Create a new table "words" with the following schema:
     - word              TEXT PRIMARY KEY NOT NULL
     - time_added        TEXT NOT NULL
     - clues             TEXT        -- (nullable)
     - clues_last_updated TEXT NOT NULL
     - status            TEXT NOT NULL CHECK(status IN ('approved','rejected','unchecked'))
     - status_last_updated TEXT NOT NULL
2. Migrate data from the old "wordlist" table:
     - word           : from wordlist.answers
     - time_added     : if wordlist.clues_last_updated is null or later than the current datetime, use current datetime;
                        otherwise, use wordlist.clues_last_updated.
     - clues          : copied as-is.
     - clues_last_updated: copied from wordlist.clues_last_updated (using current datetime if null).
     - status         : copied as-is.
     - status_last_updated: set to current datetime.
3. Drop the old "wordlist" table.

Usage:
    python migrate_wordlist_to_words.py
"""

import sqlite3
import os
import yaml
import datetime

# Load database file configuration
CONFIG_PATH = os.path.join("scripts", "config.yml")
if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"Configuration file '{CONFIG_PATH}' not found.")

with open(CONFIG_PATH, "r") as file:
    config = yaml.safe_load(file)
    DATABASE_FILE = config.get("db_file")
    if not DATABASE_FILE:
        raise ValueError("The configuration file must contain the 'db_file' key.")


def migrate(conn):
    """
    Performs the migration from the 'wordlist' table to the new 'words' table.
    """
    current_time = datetime.datetime.now().isoformat()  # current datetime as ISO string
    cur = conn.cursor()

    # 1. Create the new 'words' table.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS words (
            word TEXT PRIMARY KEY NOT NULL,
            time_added TEXT NOT NULL,
            clues TEXT,
            clues_last_updated TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('approved', 'rejected', 'unchecked')),
            status_last_updated TEXT NOT NULL
        );
    """
    )

    # 2. Migrate the data from 'wordlist' into 'words'.
    #
    # For each row in wordlist:
    # - word: from answers.
    # - time_added: if clues_last_updated is NULL or is later than the current time, use current_time; else use clues_last_updated.
    # - clues: copied as-is.
    # - clues_last_updated: if NULL, use current_time (to satisfy NOT NULL constraint).
    # - status: copied as-is.
    # - status_last_updated: always set to current_time.
    #
    # Note: We assume that 'answers' is unique in wordlist.
    cur.execute(
        """
        INSERT INTO words(word, time_added, clues, clues_last_updated, status, status_last_updated)
        SELECT 
            answers,
            CASE 
                WHEN clues_last_updated IS NULL OR clues_last_updated > ? THEN ? 
                ELSE clues_last_updated 
            END,
            clues,
            IFNULL(clues_last_updated, ?),
            status,
            ?
        FROM wordlist;
    """,
        (current_time, current_time, current_time, current_time),
    )

    # 3. Drop the old 'wordlist' table.
    cur.execute("DROP TABLE wordlist;")

    conn.commit()
    print(
        "Migration successful: 'words' table created and data migrated. 'wordlist' table dropped."
    )


def main():
    if not os.path.exists(DATABASE_FILE):
        print(f"Database file '{DATABASE_FILE}' not found.")
        return

    conn = sqlite3.connect(DATABASE_FILE)
    try:
        migrate(conn)
    except Exception as e:
        print(f"An error occurred during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
