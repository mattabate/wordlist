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
