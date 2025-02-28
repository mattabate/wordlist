"""Add words and clues to db from scored wordlist"""

import argparse
import os
import sqlite3
import tqdm
import sys
import yaml
import importlib.util

from dotenv import load_dotenv

from wordlist.lib.database import (
    add_or_update_source,
    add_word,
    create_source_word,
    get_words,
)
from wordlist.utils.parsers import load_cc_txt_as_dict
from wordlist.utils.printing import c_yellow, c_end, c_red, c_pink, c_green

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
DATABASE_FILE = os.getenv("SQLITE_DB_FILE")
CLUES_SOURCE = os.getenv("CLUES_SOURCE", "wordlist/lib/clues.template.py")


module_name = os.path.splitext(os.path.basename(CLUES_SOURCE))[0]
spec = importlib.util.spec_from_file_location(module_name, CLUES_SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fetch_clues = module.fetch_clues

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
        print(f"{c_red}Error: No input wordlist specified.{c_end}")
        parser.print_help()
        sys.exit(1)

    # 3. Build the path to the config.yml based on the --input argument
    config_path = os.path.join("sources", args.input, "config.yml")

    # Check if config file exists
    if not os.path.exists(config_path):
        print(f"{c_red}Error: Could not find config file at {config_path}{c_end}")
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
        print(f"{c_red}Error reading config file{c_end}: {e}")
        sys.exit(1)

    # 5. Main logic for adding the wordlist
    try:
        my_dict = load_cc_txt_as_dict(file_path)
    except Exception as e:
        print(f"{c_red}Error parsing wordlist{c_end}: {e}")
        sys.exit(1)

    # Connect to the DB
    conn = sqlite3.connect(DATABASE_FILE)

    # Add source
    source_id = add_or_update_source(
        conn,
        name=name,
        source_link=url,
        file_path=file_path,
    )
    if not source_id:
        print(f"{c_red}Error{c_end}: Could not add source to database.")
        conn.close()
        sys.exit(1)

    # Get existing words from DB
    words_in_db = get_words(conn)
    # Determine which words need to be added
    words_in_db_set = set(words_in_db)
    words_to_add = [w for w in my_dict if w not in words_in_db_set]

    tqdm.tqdm.write(
        f"Adding {c_yellow}{len(words_to_add)}{c_end} words to the database"
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
                    f"Clues {c_green}Found{c_end}. "
                    + f"Adding {c_yellow}{word}{c_end} to the database. "
                    + f"List score: {my_dict[word]}."
                )
            else:
                tqdm.tqdm.write(
                    f"Clues {c_pink}Not Availible{c_end}. "
                    + f"Adding {c_yellow}{word}{c_end} to the database. "
                    + f"List score: {my_dict[word]}."
                )
        else:
            clues = None
            tqdm.tqdm.write(
                f"{c_pink}Skipping{c_end} API call for without clues. "
                + f"Adding {c_yellow}{word}{c_end} to the database. "
                + f"List score: {my_dict[word]}."
            )
        add_word(conn, word, clues)

    # Add all words to this source in DB
    tqdm.tqdm.write(
        f"Associating {c_yellow}{len(my_dict)}{c_end} words with source '{name}'."
    )
    for w, score in tqdm.tqdm(my_dict.items()):
        create_source_word(conn, source_id, w, score)

    conn.close()
    print(f"{c_green}Done!{c_end}")
