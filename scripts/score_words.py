#!/usr/bin/env python3
"""
Script to find words that have no entry in 'word_model_score' for a given model.

Usage:
    python3 score_words.py --model [MODEL_ID]
"""


from typing import List, Tuple
import tqdm
import argparse
import sqlite3
import time
import os
from dotenv import load_dotenv
from models.database import get_clues_for_word, add_word_model_score
from models.svm import client, clf, add_prefix, EMB_MODL
import utils.printing


def get_words_missing_scores(conn, model_id: int) -> list[str]:
    """
    Get words in 'wordlist' that lack an entry in 'word_model_score' for this model.
    Returns an empty list if there's an error or raises, depending on how you want to handle it.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT w.answers
            FROM wordlist w
            LEFT JOIN word_model_score wms
                ON w.answers = wms.word
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


def infer(words: List[str]) -> List[Tuple[str, float]]:
    """
    Return a sorted list of (word, score) tuples, from most assumed good (score high)
    to most assumed bad (score low).
    """
    chunk_size = 1500
    words_considered = [add_prefix(w, get_clues_for_word(w)) for w in words]
    word_scores = []

    for i in tqdm.tqdm(range(0, len(words_considered), chunk_size)):
        batch_words = words_considered[i : i + chunk_size]
        response = client.embeddings.create(input=batch_words, model=EMB_MODL).data
        batch_out = [item.embedding for item in response]

        batch_scores = clf.decision_function(batch_out)

        # Note: 'j - i' aligns with batch indexing vs. global indexing
        word_scores += [
            (words[j], float(batch_scores[j - i]))
            for j in range(i, min(i + chunk_size, len(words)))
        ]

        time.sleep(0.1)  # Pause to avoid overloading

    # Sort high-to-low by decision_function score
    word_scores_sorted = sorted(word_scores, key=lambda x: x[1], reverse=True)
    return word_scores_sorted


def main():
    parser = argparse.ArgumentParser(
        description="Show words missing scores for a given model."
    )
    parser.add_argument("--model", type=int, required=True, help="Model ID to check.")
    args = parser.parse_args()

    model_id = args.model

    conn = sqlite3.connect("wordlist.db")

    words = get_words_missing_scores(conn, model_id)
    inferred_scores = infer(words)

    for word, score in tqdm.tqdm(inferred_scores):
        tqdm.tqdm.write(
            f"{utils.printing.c_yellow}Adding{utils.printing.c_end} {word}: {score}"
        )
        add_word_model_score(conn, word, model_id, score)

    conn.close()


if __name__ == "__main__":
    main()
