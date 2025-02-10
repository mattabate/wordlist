#!/usr/bin/env python3
"""
Generate a scored wordlist for a given model, normalized to [0..50],
and sorted by descending score, then alphabetically.

Usage:
    python3 generate_scored_wordlist.py --model 1
"""
import models.database
from utils.json import write_json
import sqlite3
import yaml

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    DB_PATH = config["db_file"]

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    approved_words = models.database.get_words(conn, status="approved")
    rejected_words = models.database.get_words(conn, status="rejected")
    write_json("data/outputs/approved.json", approved_words)
    write_json("data/outputs/rejected.json", rejected_words)
