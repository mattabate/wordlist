#!/usr/bin/env python3
"""
This script updates an SQLite database for the crossword wordlist using file paths 
loaded from config.yml.

It performs the updates in four phases when you use the `--create_db` flag:
    1. Initialize entries: Insert missing words (with all fields NULL except answers and a default status).
    2. Update scores: Update words that lack a score if they appear in the scored JSON.
    3. Update statuses: For words with status 'unchecked', update status from the approved/rejected JSONs.
    4. Update clues: For words without clues, call the API to fetch and update clues.

It also supports a special mode with the `--update_rankings` flag, which:
    * Only updates statuses in the DB for words that appear in the approved/rejected JSON files,
      ignoring any existing status. This is intended to quickly re-rank words after manual approval/rejection.

Usage:
  python scripts/create_db.py --help
  python scripts/create_db.py --create_db [--force]
  python scripts/create_db.py --update_rankings

Flags:
  --create_db        Create or update the database (runs phases 1–4).
  --force            If used with --create_db, deletes any existing DB file first.
  --update_rankings  Only update statuses for words in approved.json or rejected.json.
  --help             Show this help message and exit.
"""

import argparse
import sqlite3
import json
import os
import requests
import time
import random
from bs4 import BeautifulSoup
from tqdm import tqdm
import yaml  # Make sure to install PyYAML: pip install pyyaml

# Color-coded printing utilities
from utils.printing import c_red, c_green, c_yellow, c_blue, c_pink, c_end

# -----------------------------
# Load configuration from config.yml
# -----------------------------
CONFIG_FILE = "scripts/config.yml"


def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config(CONFIG_FILE)

# File paths loaded from the "create_db" section.
RAW_WORDLIST_FILE = config["create_db"]["RAW_WORDLIST"]
SCORED_WORDLIST_FILE = config["create_db"]["SCORED_WORDLIST"]
WORDS_APPROVED = config["create_db"]["WORDS_APPROVED"]
WORDS_REJECTED = config["create_db"]["WORDS_REJECTED"]
DATABASE_FILE = config["create_db"].get("DATABASE_FILE", "wordlist.db")

# Number of clues to retrieve per word.
_NUM_CLUES = 6


# -----------------------------
# Functions
# -----------------------------
def fetch_clues(word):
    """
    Fetch clues for a word from crosswordtracker.com.
    If no clues are found, returns None.
    """
    url = f"https://crosswordtracker.com/answer/{word.lower()}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CrosswordDBUpdater/1.0; +https://github.com/mattabate/wordlist)"
    }
    params = {}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        code = response.status_code
    except Exception as e:
        tqdm.write(
            f"{c_red}Warning{c_end}: Exception occurred while fetching clues for {word}: {e}"
        )
        code = None

    # If the request was unsuccessful, return None
    if code != 200:
        return None

    # Otherwise, parse the HTML
    time.sleep(random.uniform(0.15, 0.2))  # small delay to be nice to the server
    soup = BeautifulSoup(response.text, "html.parser")
    clue_header = soup.find("h3", string="Referring crossword puzzle clues")
    if clue_header:
        clue_container = clue_header.find_next_sibling("div")
        if clue_container:
            li_items = clue_container.find_all("li")
            if li_items:
                clues_text = "\n".join(
                    [f"- {li.get_text(strip=True)}" for li in li_items[:_NUM_CLUES]]
                )
                return clues_text
    return None


def get_clues_for_word(word: str, db_path: str = DATABASE_FILE) -> str:
    """
    Returns the clues string from the 'wordlist' table for a given word.
    If the word is not found or has no clues, returns None.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Convert the input word to uppercase to match your DB's stored answers
        cursor.execute("SELECT clues FROM wordlist WHERE answers = ?", (word.upper(),))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def load_json_file(filename):
    """
    Loads and returns the JSON content from a file.
    Raises an error if the file does not exist.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File not found: {filename}")
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


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


def get_words(conn, status=""):
    """
    Fetches words and their clues from the database filtered by status.
    If no status is provided, it fetches all words.
    """
    cur = conn.cursor()
    if status:
        query = "SELECT answers, clues FROM wordlist WHERE status = ?;"
        cur.execute(query, (status,))
    else:
        query = "SELECT answers, clues FROM wordlist;"
        cur.execute(query)

    rows = cur.fetchall()
    return {answer: clues for answer, clues in rows}


# -----------------------------
# Update functions
# -----------------------------
def initialize_entries(conn):
    """
    (1) Inserts missing words into the database.
    Loads all words from RAW, REJECTED, and APPROVED JSONs.
    For any word not already in the DB, inserts an entry with:
      - answers = word
      - clues, scores set to NULL
      - status determined by the JSONs.
    """
    raw_words = set(load_json_file(RAW_WORDLIST_FILE))
    rejected_set = set(load_json_file(WORDS_REJECTED))
    approved_set = set(load_json_file(WORDS_APPROVED))
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
    scored_dict = load_json_file(SCORED_WORDLIST_FILE)
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
    approved_set = set(load_json_file(WORDS_APPROVED))
    rejected_set = set(load_json_file(WORDS_REJECTED))
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
        clues = fetch_clues(word)
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


def update_rankings(conn):
    """
    Only update the status for words in approved.json or rejected.json, and
    count how many actually changed.

    This forces the status to 'approved' or 'rejected' only if
    the current status is different from the target status.
    """
    approved_set = set(load_json_file(WORDS_APPROVED))
    rejected_set = set(load_json_file(WORDS_REJECTED))

    cur = conn.cursor()
    changed_count = 0

    # Update all approved words (only if status != 'approved')
    for word in approved_set:
        cur.execute(
            """
            UPDATE wordlist
            SET status = 'approved'
            WHERE answers = UPPER(?) AND status != 'approved'
            """,
            (word,),
        )
        changed_count += cur.rowcount

    # Update all rejected words (only if status != 'rejected')
    for word in rejected_set:
        cur.execute(
            """
            UPDATE wordlist
            SET status = 'rejected'
            WHERE answers = UPPER(?) AND status != 'rejected'
            """,
            (word,),
        )
        changed_count += cur.rowcount

    conn.commit()
    print(
        f"{c_green}Actually updated status for {changed_count} entries (rankings).{c_end}"
    )


# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Update or create the crossword wordlist database.",
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
    parser.add_argument(
        "--update_rankings",
        action="store_true",
        help="Only update DB status for words in approved.json or rejected.json.",
    )
    # Note: argparse automatically adds a --help flag

    args = parser.parse_args()

    # If user wants to only update rankings, do that and exit.
    if args.update_rankings:
        conn = sqlite3.connect(DATABASE_FILE)
        try:
            update_rankings(conn)
        except Exception as e:
            print(f"{c_red}Error while updating rankings:{c_end} {e}")
            conn.rollback()
        finally:
            conn.close()
        return

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
        # If neither --create_db nor --update_rankings was provided, just show help.
        parser.print_help()


if __name__ == "__main__":
    main()
