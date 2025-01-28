"""this script adds a wordlist to the database"""

import sqlite3
import tqdm
import utils.printing
from models.database import (
    add_source,
    create_source_word,
    is_word_in_db,
    add_word,
    get_words,
)

from utils.wordlist import parse_file_to_dict


DATABASE_FILE = "wordlist.db"
name = "spreadthewordlist"
url = "https://www.spreadthewordlist.com/wordlist"
file_path = "data/sources/spreadthewordlist/spreadthewordlist.txt"

if __name__ == "__main__":
    my_dict = parse_file_to_dict(file_path)

    # add source:
    conn = sqlite3.connect(DATABASE_FILE)
    source_id = add_source(
        conn,
        name=name,
        source_link=url,
        file_path=file_path,
    )

    if not source_id:
        print(
            f"{utils.printing.c_red}Error{utils.printing.c_red}:find this{utils.printing.c_end}"
        )
        exit()

    words_in_wordslist = [s for s in my_dict.keys()]
    words_in_db = get_words(conn)

    # get all words in the wordlist that are not in the database
    words_to_add = set(words_in_wordslist) - set(words_in_db)
    tqdm.tqdm.write(
        f"Adding {utils.printing.c_yellow}{len(words_to_add)}{utils.printing.c_end} words to the database"
    )
    words_to_add = list(words_to_add)
    # sort by score in wordlist
    words_to_add.sort(key=lambda x: my_dict[x], reverse=True)
    for word in tqdm.tqdm(words_to_add):
        tqdm.tqdm.write(
            f"Adding {utils.printing.c_yellow}{word}{utils.printing.c_end} to the database. List score: {my_dict[word]}"
        )
        add_word(conn, word)

    # add words to the source
    tqdm.tqdm.write(
        f"Adding {utils.printing.c_yellow}{len(my_dict)}{utils.printing.c_end} words to the source"
    )
    for k, v in tqdm.tqdm(my_dict.items()):
        create_source_word(conn, source_id, k, v)

    conn.close()
