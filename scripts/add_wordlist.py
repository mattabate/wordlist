import argparse
import os
import sys
import yaml
import sqlite3
import tqdm

import utils.printing
from models.database import (
    add_source,
    create_source_word,
    add_word,
    get_words,
    fetch_clues,
)
from utils.wordlist import parse_file_to_dict

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    DATABASE_FILE = config["db_file"]

if __name__ == "__main__":

    # 1. Parse command-line arguments
    parser = argparse.ArgumentParser(description="Add a wordlist to the database.")
    parser.add_argument(
        "--input",
        "-i",
        help="Name of the wordlist folder to load config from (e.g., 'spreadthewordlist').",
    )
    parser.add_argument(
        "--skip_clues",
        action="store_true",
        help="If set, clues will be skipped.",
    )
    args = parser.parse_args()
    f_skip_clues = args.skip_clues
    # 2. If no input provided, print help and exit
    if not args.input:
        print(
            f"{utils.printing.c_red}Error: No input wordlist specified.{utils.printing.c_end}"
        )
        parser.print_help()
        sys.exit(1)

    # 3. Build the path to the config.yml based on the --input argument
    config_path = os.path.join("data", "sources", args.input, "config.yml")

    # Check if config file exists
    if not os.path.exists(config_path):
        print(
            f"{utils.printing.c_red}Error: Could not find config file at {config_path}{utils.printing.c_end}"
        )
        sys.exit(1)

    # 4. Load parameters from config.yml
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Extract parameters from YAML
        name = config["name"]
        url = config["url"]
        file_path = config["file_path"]

    except Exception as e:
        print(
            f"{utils.printing.c_red}Error reading config file: {e}{utils.printing.c_end}"
        )
        sys.exit(1)

    # 5. Main logic for adding the wordlist
    try:
        my_dict = parse_file_to_dict(file_path)
    except Exception as e:
        print(
            f"{utils.printing.c_red}Error parsing wordlist: {e}{utils.printing.c_end}"
        )
        sys.exit(1)

    # Connect to the DB
    conn = sqlite3.connect(DATABASE_FILE)

    # Add source
    source_id = add_source(
        conn,
        name=name,
        source_link=url,
        file_path=file_path,
    )
    if not source_id:
        print(
            f"{utils.printing.c_red}Error: Could not add source to database.{utils.printing.c_end}"
        )
        conn.close()
        sys.exit(1)

    # Get existing words from DB
    words_in_db = get_words(conn)
    # Determine which words need to be added
    words_in_db_set = set(words_in_db)
    words_to_add = [w for w in my_dict if w not in words_in_db_set]

    tqdm.tqdm.write(
        f"Adding {utils.printing.c_yellow}{len(words_to_add)}{utils.printing.c_end} words to the database"
    )

    # Sort by score (descending) in the parsed dict
    words_to_add.sort(key=lambda x: my_dict[x], reverse=True)

    # Add missing words
    for word in tqdm.tqdm(words_to_add):
        word_upper = word.upper()
        if not f_skip_clues:
            clues = fetch_clues(word=word_upper)
            if clues:
                tqdm.tqdm.write(
                    f"Clues {utils.printing.c_green}Found{utils.printing.c_end}. "
                    + f"Adding {utils.printing.c_yellow}{word}{utils.printing.c_end} to the database. "
                    + f"List score: {my_dict[word]}."
                )
            else:
                tqdm.tqdm.write(
                    f"Clues {utils.printing.c_pink}Not Availible{utils.printing.c_end}. "
                    + f"Adding {utils.printing.c_yellow}{word}{utils.printing.c_end} to the database. "
                    + f"List score: {my_dict[word]}."
                )
        else:
            clues = None
            tqdm.tqdm.write(
                f"{utils.printing.c_pink}Skipping{utils.printing.c_end} API call for without clues. "
                + f"Adding {utils.printing.c_yellow}{word}{utils.printing.c_end} to the database. "
                + f"List score: {my_dict[word]}."
            )
        add_word(conn, word, clues)

    # Add all words to this source in DB
    tqdm.tqdm.write(
        f"Associating {utils.printing.c_yellow}{len(my_dict)}{utils.printing.c_end} words with source '{name}'."
    )
    for w, score in tqdm.tqdm(my_dict.items()):
        create_source_word(conn, source_id, w, score)

    conn.close()
    print(f"{utils.printing.c_green}Done!{utils.printing.c_end}")
