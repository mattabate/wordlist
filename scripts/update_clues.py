#!/usr/bin/env python3
"""
Script to update missing clues in the 'words' table.

Usage:
  python update_words.py
"""

import os
import sqlite3
import tqdm
import importlib.util

from dotenv import load_dotenv

from wordlist.lib.database import add_clue_to_word, add_clue, get_words_with_no_clues
from wordlist.utils.printing import c_green, c_yellow, c_end

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("SQLITE_DB_FILE")
CLUES_SOURCE = os.getenv("CLUES_SOURCE", "wordlist/lib/clues.template.py")

if CLUES_SOURCE == "wordlist/lib/clues.template.py" or not CLUES_SOURCE:
    print(
        c_yellow
        + "Warning"
        + c_end
        + ": this script requires you to define a function for fetching clues. See https://github.com/mattabate/wordlist/blob/main/README.md for further details."
    )
    print(c_yellow + "Shutting down" + c_end)
    exit()

# Get the Fetch clues function from the clues source provided in your env
module_name = os.path.splitext(os.path.basename(CLUES_SOURCE))[0]
spec = importlib.util.spec_from_file_location(module_name, CLUES_SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fetch_clues = module.fetch_clues


def update_clues_for_word(conn: sqlite3.Connection, word: str) -> None:
    """
    Given a word, fetch its clues from an external API (fetch_clues)
    and, if successful, update both the 'clues' and 'clues_last_updated'
    fields in the 'words' table.
    """
    clues = fetch_clues(word)
    if clues:  # only update if clues is not empty
        for c in clues:
            add_clue(conn, c)
            add_clue_to_word(conn, word, c)
        return True
    else:
        return False


def main():
    # 1. Connect to DB
    conn = sqlite3.connect(DB_PATH)

    words_to_check = get_words_with_no_clues(conn)
    # 3. Loop and update each missing word
    found_so_far = 0
    for word in tqdm.tqdm(words_to_check, desc="Updating missing clues"):
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
