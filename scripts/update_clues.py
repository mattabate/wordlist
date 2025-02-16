#!/usr/bin/env python3
"""
Script to update missing clues in the 'words' table.

Usage:
  python update_words.py
"""

import os
import sqlite3
import tqdm

from dotenv import load_dotenv

from wordlist.utils.printing import c_green, c_yellow, c_end
from wordlist.lib.database import update_clues_for_word

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("SQLITE_DB_FILE")


def main():
    # 1. Connect to DB
    conn = sqlite3.connect(DB_PATH)

    # 2. Get words with missing or empty clues, sorted by `clues_last_updated` (earliest first)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT word
        FROM words
        WHERE clues IS NULL OR clues = ''
        ORDER BY clues_last_updated ASC
    """
    )
    rows = [row[0] for row in cur.fetchall()]

    found_so_far = 0
    # 3. Loop and update each missing word
    for word in tqdm.tqdm(rows, desc="Updating missing clues"):
        if update_clues_for_word(conn, word):
            tqdm.tqdm.write(
                f"{c_green}Added{c_end} clues for word '{word}'. Found so far: {found_so_far}"
            )
            found_so_far += 1
        else:
            tqdm.tqdm.write(
                f"{c_yellow}Failed{c_end} to update clues for word '{word}'. Found so far: {found_so_far}"
            )

    # 4. Cleanup
    conn.close()


if __name__ == "__main__":
    main()
