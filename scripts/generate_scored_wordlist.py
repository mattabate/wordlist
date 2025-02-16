#!/usr/bin/env python3
"""
Generate a scored wordlist for a given model, normalized to [0..50],
and sorted by descending score, then alphabetically.

Usage:
    python3 generate_scored_wordlist.py --model 1
"""

import argparse
import json
import os
import sqlite3

from dotenv import load_dotenv

import wordlist.lib.database
from wordlist.utils.json import write_json
from wordlist.utils.printing import c_red, c_green, c_yellow, c_end


load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

DATABASE_FILE = os.getenv("SQLITE_DB_FILE")
SCORED_WORDLIST_TXT = "outputs/scored_wordlist.txt"
SCORED_WORDLIST_JSON = "outputs/scored_wordlist.json"


def main():
    # 1. Parse arguments
    parser = argparse.ArgumentParser(
        description="Generate a normalized scored wordlist for a given model."
    )
    parser.add_argument("--model", type=int, required=True, help="Model ID to process.")
    parser.add_argument(
        "--full", action="store_true", help="Enable full mode with extended processing."
    )
    args = parser.parse_args()
    model_id = args.model

    # 3. Connect to DB & fetch scores for this model
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()

    if args.full:
        cur.execute(
            """
            SELECT wms.word, wms.score, w.status
            FROM word_model_score wms
            JOIN words w
                ON wms.word = w.word
            WHERE wms.model = ?
            AND w.status != 'rejected'
            """,
            (model_id,),
        )
    else:
        cur.execute(
            """
            SELECT wms.word, wms.score, w.status
            FROM word_model_score wms
            JOIN words w
                ON wms.word = w.word
            WHERE wms.model = ?
            AND w.status != 'rejected'
            AND (w.status = 'approved' OR wms.score>0.3)
            """,
            (model_id,),
        )
    results = cur.fetchall()
    conn.close()

    if not results:
        print(f"{c_yellow}No scores found for model {model_id}.{c_end}")
        return

    # 4. Separate into (word, raw_score)
    #    Sort primarily by score descending, secondarily by word ascending

    unchecked_words_and_scores = [
        (row[0], min(float(row[1]), 1.0)) for row in results if row[2] == "unchecked"
    ]
    min_score_unchecked = min([x for _, x in unchecked_words_and_scores], default=0)
    approved_words_and_scores = [
        (row[0], min(max(float(row[1]), min_score_unchecked), 1))
        for row in results
        if row[2] == "approved"
    ]

    words_and_scores = unchecked_words_and_scores + approved_words_and_scores
    words_and_scores.sort(key=lambda x: (-x[1], x[0]))
    word_closest_to_zero = min(words_and_scores, key=lambda x: abs(x[1]))
    closest_word, closest_score = word_closest_to_zero

    # 5. Determine min & max raw scores
    min_score = min(words_and_scores, key=lambda x: x[1])[1]
    max_score = max(words_and_scores, key=lambda x: x[1])[1]
    score_range = max_score - min_score

    # 6. Normalize to [0..50]
    normalized_dict = {}
    if score_range == 0:
        # If all scores are identical
        print(f"{c_red}All scores are identical. Normalizing to 25 by default.{c_end}")
        for w, s in words_and_scores:
            normalized_dict[w] = 25
    else:
        for w, s in words_and_scores:
            normalized_value = (s - min_score) / score_range * 50
            normalized_dict[w] = int(normalized_value)

    print(
        f"{c_yellow}Word with closest model score to zero: {closest_word} ({closest_score:.2f}){c_end}. New score: {normalized_dict[closest_word]}."
    )
    print(f"{c_yellow}Number of Words: {len(words_and_scores)}{c_end}")

    # 7. Write out the JSON dict of {word: normalized_score}
    #    in the sorted order (in Python >=3.7, dicts preserve insertion order)
    ordered_dict_for_json = {}
    for w, _ in words_and_scores:
        ordered_dict_for_json[w] = normalized_dict[w]

    with open(SCORED_WORDLIST_JSON, "w", encoding="utf-8") as f:
        json.dump(ordered_dict_for_json, f, indent=4)

    # 8. Write out the sorted list of words (descending by raw score, then alpha)
    sorted_word_list = [w for (w, _) in words_and_scores]

    # 9. Write out a TXT file: "word;score" using the normalized score in the same order
    with open(SCORED_WORDLIST_TXT, "w", encoding="utf-8") as f:
        for w in sorted_word_list:
            f.write(f"{w};{normalized_dict[w]}\n")

    print(f"{c_green}Done!{c_end} Generated scored wordlist for model {model_id}.")

    conn = sqlite3.connect(DATABASE_FILE)
    approved_words = wordlist.lib.database.get_words(conn, status="approved")
    rejected_words = wordlist.lib.database.get_words(conn, status="rejected")
    write_json("outputs/approved.json", approved_words)
    write_json("outputs/rejected.json", rejected_words)

    conn.close()


if __name__ == "__main__":
    main()
