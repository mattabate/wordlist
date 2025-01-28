#!/usr/bin/env python3
"""
Script to ONLY update the rankings (statuses) for words from approved.json or rejected.json.

Usage:
    python update_rankings.py

No flags are required.
"""

import os
import sqlite3
import yaml
from utils.printing import c_red, c_green, c_end

import utils.json
import models.database

CONFIG_FILE = "scripts/config.yml"


def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def update_rankings(conn, approved_json, rejected_json):
    """
    Only update the status for words in approved.json or rejected.json,
    and count how many actually changed.
    """
    approved_set = set(utils.json.load_json(approved_json))
    rejected_set = set(utils.json.load_json(rejected_json))

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


def main():
    config = load_config(CONFIG_FILE)
    database_file = config["create_db"].get("DATABASE_FILE", "wordlist.db")
    approved_json = config["create_db"]["WORDS_APPROVED"]
    rejected_json = config["create_db"]["WORDS_REJECTED"]

    if not os.path.exists(database_file):
        print(f"{c_red}Error: Database file does not exist at '{database_file}'{c_end}")
        return

    conn = sqlite3.connect(database_file)
    try:
        update_rankings(conn, approved_json, rejected_json)
    except Exception as e:
        print(f"{c_red}Error while updating rankings:{c_end} {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
