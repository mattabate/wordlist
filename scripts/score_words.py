#!/usr/bin/env python3
"""
Script to find words that have no entry in 'word_model_score' for a given model.

Usage:
    python3 score_words.py --model [MODEL_ID]
"""
import argparse
import os
import pickle
import sqlite3
import time
import tqdm

from dotenv import load_dotenv

from wordlist.lib.svm import client, add_prefix, EMB_MODL
from wordlist.lib.database import (
    get_clues_for_word,
    add_word_model_score,
    get_model_pkl_file_name,
)

from wordlist.utils.printing import c_yellow, c_end

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

DB_PATH = os.getenv("SQLITE_DB_FILE")


def get_words_missing_scores(conn, model_id: int) -> list[str]:
    """
    Get words in 'words' that lack an entry in 'word_model_score' for this model.
    Returns an empty list if there's an error or raises, depending on how you want to handle it.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT w.word
            FROM words w
            LEFT JOIN word_model_score wms
                ON w.word = wms.word
                AND wms.model = ?
            WHERE wms.word IS NULL
            """,
            (model_id,),
        )
        rows = [row[0] for row in cur.fetchall()]
        return rows

    except Exception as e:
        # log, print, or handle error as needed
        print(f"Error fetching words missing scores for model {model_id}: {e}")
        # either re-raise or return an empty list:
        # raise
        return []


# ------------------------------------------------------------------------------
#  Inference Function
# ------------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Show words missing scores for a given model."
    )
    parser.add_argument("--model", type=int, required=True, help="Model ID to check.")
    args = parser.parse_args()

    model_id = args.model

    conn = sqlite3.connect(DB_PATH)
    PKL_FILE = get_model_pkl_file_name(conn, model_id)

    words = get_words_missing_scores(conn, model_id)

    chunk_size = 1500
    words_considered = [add_prefix(w, get_clues_for_word(w)) for w in words]
    word_scores = []
    with open(PKL_FILE, "rb") as file:
        clf = pickle.load(file)

    for i in tqdm.tqdm(range(0, len(words_considered), chunk_size)):
        batch_words = words_considered[i : i + chunk_size]
        response = client.embeddings.create(input=batch_words, model=EMB_MODL).data
        batch_out = [item.embedding for item in response]

        batch_scores = clf.decision_function(batch_out)

        # Note: 'j - i' aligns with batch indexing vs. global indexing
        new_words = [
            (words[j], float(batch_scores[j - i]))
            for j in range(i, min(i + chunk_size, len(words)))
        ]

        for word, score in tqdm.tqdm(new_words):
            tqdm.tqdm.write(f"{c_yellow}Adding{c_end} {word}: {score}")
            add_word_model_score(conn, word, model_id, score)
        word_scores += new_words

        time.sleep(0.1)  # Pause to avoid overloading

    conn.close()


if __name__ == "__main__":
    main()
