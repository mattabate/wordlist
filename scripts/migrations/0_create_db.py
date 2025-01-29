#!/usr/bin/env python3
"""
Create or update the crossword wordlist database.

Usage:
    python create_db.py --create_db [--force]
"""

import argparse
import os
import sqlite3
import yaml
from tqdm import tqdm

import models.database
import utils.json
from utils.printing import c_red, c_green, c_yellow, c_blue, c_end

CONFIG_FILE = "scripts/config.yml"


def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# -----------------------------
# Load configuration from config.yml
# -----------------------------
config = load_config(CONFIG_FILE)
RAW_WORDLIST_FILE = config["create_db"]["RAW_WORDLIST"]
SCORED_WORDLIST_FILE = config["create_db"]["SCORED_WORDLIST"]
WORDS_APPROVED = config["create_db"]["WORDS_APPROVED"]
WORDS_REJECTED = config["create_db"]["WORDS_REJECTED"]
DATABASE_FILE = config["db_file"]


# -----------------------------
# Update functions
# -----------------------------


def create_table(conn):
    """
    Creates the 'wordlist' table in the connected SQLite database.
    'answers' and 'status' are defined as NOT NULL.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS wordlist (
        answers TEXT NOT NULL PRIMARY KEY CHECK(length(answers) BETWEEN 2 AND 40 AND answers = UPPER(answers)),
        clues   TEXT,
        scores  INTEGER CHECK (scores IS NULL OR scores < 100),
        status  TEXT NOT NULL CHECK( status IN ('unchecked','approved','rejected') )
    );
    """
    conn.execute(create_table_sql)
    conn.commit()


def create_indexes(conn):
    """
    Creates indexes on columns to facilitate fast searching.
    """
    conn.execute("CREATE INDEX IF NOT EXISTS idx_answers ON wordlist(answers);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scores ON wordlist(scores);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON wordlist(status);")
    conn.commit()


def print_schema(conn):
    """
    Prints the schema for the 'wordlist' table.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(wordlist);")
    rows = cursor.fetchall()
    print("\nDatabase schema for table 'wordlist':")
    print(
        "{:<5} {:<10} {:<20} {:<8} {:<10} {:<5}".format(
            "cid", "name", "type", "notnull", "dflt_value", "pk"
        )
    )
    print("-" * 60)
    for row in rows:
        cid, name, type_, notnull, dflt_value, pk = row
        print(
            "{:<5} {:<10} {:<20} {:<8} {:<10} {:<5}".format(
                cid, name, type_, notnull, str(dflt_value), pk
            )
        )
    print()


def initialize_entries(conn):
    """
    (1) Inserts missing words into the database.
    Loads all words from RAW, REJECTED, and APPROVED JSONs.
    For any word not already in the DB, inserts an entry with:
      - answers = word
      - clues, scores set to NULL
      - status determined by the JSONs.
    """
    raw_words = set(utils.json.load_json(RAW_WORDLIST_FILE))
    rejected_set = set(utils.json.load_json(WORDS_REJECTED))
    approved_set = set(utils.json.load_json(WORDS_APPROVED))
    all_words = raw_words.union(rejected_set).union(approved_set)

    cur = conn.cursor()
    cur.execute("SELECT answers FROM wordlist;")
    existing = set(row[0] for row in cur.fetchall())

    new_entries = all_words - existing
    tqdm.write(
        f"{c_blue}Initializing entries: inserting {len(new_entries)} new words...{c_end}"
    )

    processed = 0
    inserted = 0
    for word in tqdm(
        sorted(new_entries), desc="Inserting new entries", total=len(new_entries)
    ):
        if word in rejected_set:
            status = "rejected"
        elif word in approved_set:
            status = "approved"
        else:
            status = "unchecked"
        try:
            cur.execute(
                "INSERT INTO wordlist (answers, clues, scores, status) VALUES (?, ?, ?, ?);",
                (word.upper(), None, None, status),
            )
            inserted += 1
        except sqlite3.IntegrityError as e:
            tqdm.write(f"{c_red}Error{c_end}: Inserting {word}: {e}")
        processed += 1
        if processed % 10 == 0:
            conn.commit()
    conn.commit()
    tqdm.write(f"{c_green}Inserted {inserted} new entries.{c_end}")


def update_scores(conn):
    """
    (2) Updates scores for words lacking a score.
    """
    scored_dict = utils.json.load_json(SCORED_WORDLIST_FILE)
    cur = conn.cursor()
    words = sorted(scored_dict.keys())
    tqdm.write(f"{c_blue}Updating scores for {len(words)} words...{c_end}")
    processed = 0
    updated = 0
    for word in tqdm(words, desc="Updating scores", total=len(words)):
        cur.execute("SELECT scores FROM wordlist WHERE answers = ?", (word.upper(),))
        row = cur.fetchone()
        if row is not None:
            current_score = row[0]
            if current_score is None:
                score = scored_dict[word]
                cur.execute(
                    "UPDATE wordlist SET scores = ? WHERE answers = ?",
                    (score, word.upper()),
                )
                updated += 1
        processed += 1
        if processed % 10 == 0:
            conn.commit()
    conn.commit()
    tqdm.write(f"{c_green}Updated scores for {updated} words.{c_end}")


def update_statuses(conn):
    """
    (3) Updates statuses for words currently marked as 'unchecked'.
    """
    approved_set = set(utils.json.load_json(WORDS_APPROVED))
    rejected_set = set(utils.json.load_json(WORDS_REJECTED))
    cur = conn.cursor()
    cur.execute("SELECT answers, status FROM wordlist WHERE status = 'unchecked'")
    rows = cur.fetchall()
    tqdm.write(f"{c_blue}Updating statuses for {len(rows)} 'unchecked' words...{c_end}")
    processed = 0
    updated = 0
    for word, status in tqdm(rows, desc="Updating statuses", total=len(rows)):
        new_status = None
        if word in rejected_set:
            new_status = "rejected"
        elif word in approved_set:
            new_status = "approved"

        if new_status and new_status != status:
            cur.execute(
                "UPDATE wordlist SET status = ? WHERE answers = ?",
                (new_status, word),
            )
            updated += 1

        processed += 1
        if processed % 10 == 0:
            conn.commit()
    conn.commit()
    tqdm.write(f"{c_green}Updated status for {updated} words.{c_end}")


def update_clues(conn):
    """
    (4) For all words with NULL clues, call the API to fetch clues and update the row.
    """
    cur = conn.cursor()
    cur.execute("SELECT answers FROM wordlist WHERE clues IS NULL")
    rows = [row[0] for row in cur.fetchall()]
    total = len(rows)
    tqdm.write(f"{c_blue}Fetching clues for {total} words...{c_end}")
    processed = 0
    updated = 0
    for word in tqdm(sorted(rows), desc="Updating clues", total=total):
        clues = models.database.fetch_clues(word)
        cur.execute("UPDATE wordlist SET clues = ? WHERE answers = ?", (clues, word))
        if clues is not None:
            tqdm.write(f"{c_yellow}Updated{c_end} word '{word}' with new clues.")
        else:
            tqdm.write(f"{c_blue}Skipping{c_end} word '{word}'. No clues found.")
        processed += 1
        updated += 1
        if processed % 10 == 0:
            conn.commit()
    conn.commit()
    tqdm.write(f"{c_green}Updated clues for {updated} words.{c_end}")


def main():
    parser = argparse.ArgumentParser(
        description="Create or update the crossword wordlist database.",
        epilog="Run with --help to see available options.",
    )
    parser.add_argument(
        "--create_db",
        action="store_true",
        help="Create or update the database (runs phases 1–4).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="If used with --create_db, deletes the existing database first.",
    )
    args = parser.parse_args()

    # If user wants to create or update the DB (main pipeline):
    if args.create_db:
        # If --force, remove existing database
        if args.force and os.path.exists(DATABASE_FILE):
            print(
                f"{c_red}Force flag detected:{c_end} Removing existing database file."
            )
            os.remove(DATABASE_FILE)

        conn = sqlite3.connect(DATABASE_FILE)
        try:
            print("Creating table...")
            create_table(conn)
            print("Creating indexes...")
            create_indexes(conn)
            print_schema(conn)

            # Phase 1: Initialize entries (insert any missing words)
            initialize_entries(conn)

            # Phase 2: Update scores
            update_scores(conn)

            # Phase 3: Update statuses
            update_statuses(conn)

            # Phase 4: Update clues
            update_clues(conn)

        except Exception as e:
            print(f"{c_red}Error:{c_end} {e}")
            conn.rollback()
        finally:
            conn.close()
    else:
        # If neither --create_db nor --force was provided, just show help.
        parser.print_help()


if __name__ == "__main__":
    main()
