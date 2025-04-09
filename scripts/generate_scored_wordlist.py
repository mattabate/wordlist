#!/usr/bin/env python3
"""
Generate a scored wordlist for a given model, normalized to [0..50],
and sorted by descending score, then alphabetically.

Usage:
    python3 generate_scored_wordlist.py --model 1 [--min_score 0.8]
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
    max_score = 50
    approvd_min_score = 25
    rejected_max_score = 10
    min_score = 0
    # 1. Parse arguments
    parser = argparse.ArgumentParser(
        description="Generate a normalized scored wordlist for a given model."
    )
    parser.add_argument("--model", type=int, required=True, help="Model ID to process.")
    parser.add_argument(
        "--min_score",
        type=float,
        default=None,
        help="Minimum raw score cutoff to include a word (unless it is approved). If not provided, all words (except rejected ones) are included.",
    )
    parser.add_argument(
        "--rescore_source",
        type=str,
        default=None,
        help="Minimum raw score cutoff to include a word (unless it is approved). If not provided, all words (except rejected ones) are included.",
    )
    args = parser.parse_args()
    model_id = args.model
    min_score_cutoff = args.min_score
    rescore_source = args.rescore_source

    # 2. Connect to DB & fetch scores for this model
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()

    if not rescore_source:
        cmd = """
        SELECT wms.word, wms.score, w.status
        FROM word_model_score wms
        JOIN words w
            ON wms.word = w.word
        WHERE wms.model = ?
        AND w.status != 'rejected'
        """
        if min_score_cutoff is not None:
            # Include words that are either approved or have a score above the given cutoff
            cmd += " AND (w.status = 'approved' OR wms.score > ?)"
            cur.execute(cmd, (model_id, min_score_cutoff))
        else:
            # Include all words (except rejected)
            cur.execute(cmd, (model_id,))
    else:
        # help me figure out what should go here if anything
        cmd = """
        SELECT w.word, wms.score, w.status
        FROM word_model_score wms
        JOIN words w
            ON wms.word = w.word
        JOIN source_word sw
            ON wms.word = sw.word_id
        JOIN sources s
            ON sw.source_id = s.id
        WHERE wms.model = ? 
        AND s.name = ?
        """
        cur.execute(
            cmd,
            (
                model_id,
                rescore_source,
            ),
        )

    results = cur.fetchall()
    conn.close()

    if not results:
        print(f"{c_yellow}No scores found for model {model_id}.{c_end}")
        return

    # 3. Separate into (word, raw_score)
    #    Sort primarily by score descending, secondarily by word ascending

    rejected_words_and_scores = [
        (row[0], min(float(row[1]), 2)) for row in results if row[2] == "rejected"
    ]
    rejected_words_and_scores.sort(key=lambda x: (-x[1], x[0]))
    num_rejected_words = len(rejected_words_and_scores)
    rejected_words_and_scores = [
        (
            c[0],
            rejected_max_score - round(rejected_max_score * (i / num_rejected_words)),
        )
        for i, c in enumerate(rejected_words_and_scores)
    ]

    unchecked_words_and_scores = [
        (row[0], min(float(row[1]), 2)) for row in results if row[2] == "unchecked"
    ]
    unchecked_words_and_scores.sort(key=lambda x: (-x[1], x[0]))
    num_unchecked_words = len(unchecked_words_and_scores)
    unchecked_words_and_scores = [
        (c[0], max_score - round(max_score * (i / num_unchecked_words)))
        for i, c in enumerate(unchecked_words_and_scores)
    ]
    unchecked_words_and_scores.sort(key=lambda x: (-x[1], x[0]))
    print("top 5 unchecked words", unchecked_words_and_scores[:10])
    print("bottom 5 unchecked words", unchecked_words_and_scores[-10:])

    approved_words_and_scores = [
        (row[0], min(max(float(row[1]), 0), 2))
        for row in results
        if row[2] == "approved"
    ]
    approved_words_and_scores.sort(key=lambda x: (-x[1], x[0]))
    # scale from 25 - 50
    num_approved_words = len(approved_words_and_scores)
    approved_words_and_scores = [
        (c[0], max_score - round(approvd_min_score * (i / num_approved_words)))
        for i, c in enumerate(approved_words_and_scores)
    ]
    approved_words_and_scores.sort(key=lambda x: (-x[1], x[0]))

    print()
    print("top 5 approved words", approved_words_and_scores[:5])
    print("bottom 5 approved words", approved_words_and_scores[-5:])
    # scale from 25 - 50

    # remove all unchecked words with score < 0
    words_and_scores = (
        rejected_words_and_scores
        + unchecked_words_and_scores
        + approved_words_and_scores
    )
    words_and_scores.sort(key=lambda x: (-x[1], x[0]))
    print()
    print("top 5 words", words_and_scores[:5])

    word_closest_to_zero = min(words_and_scores, key=lambda x: abs(25 - x[1]))
    closest_word, closest_score = word_closest_to_zero

    # 4. Determine min & max raw scores
    min_score = min(words_and_scores, key=lambda x: x[1])[1]
    max_score = max(words_and_scores, key=lambda x: x[1])[1]
    score_range = max_score - min_score

    # 5. Normalize to [0..50]
    ordered_dict_for_json = {}
    if score_range == 0:
        # If all scores are identical
        print(f"{c_red}All scores are identical. Normalizing to 25 by default.{c_end}")
        for w, s in words_and_scores:
            ordered_dict_for_json[w] = 25
    else:
        for w, s in words_and_scores:
            ordered_dict_for_json[w] = s

    print(
        f"{c_yellow}Word with closest model score to zero: {closest_word} ({closest_score:.2f}){c_end}. New score: {ordered_dict_for_json[closest_word]}."
    )
    print(f"{c_yellow}Number of Words: {len(words_and_scores)}{c_end}")

    # 6. Write out the JSON dict of {word: normalized_score}
    #    in the sorted order (in Python >=3.7, dicts preserve insertion order)

    with open(SCORED_WORDLIST_JSON, "w", encoding="utf-8") as f:
        json.dump(ordered_dict_for_json, f, indent=4)

    # 7. Write out the sorted list of words (descending by raw score, then alpha)
    sorted_word_list = [w for (w, _) in words_and_scores]

    # 8. Write out a TXT file: "word;score" using the normalized score in the same order
    with open(SCORED_WORDLIST_TXT, "w", encoding="utf-8") as f:
        for w in sorted_word_list:
            f.write(f"{w};{ordered_dict_for_json[w]}\n")

    print(f"{c_green}Done!{c_end} Generated scored wordlist for model {model_id}.")

    conn = sqlite3.connect(DATABASE_FILE)
    approved_words = wordlist.lib.database.get_words(conn, status="approved")
    rejected_words = wordlist.lib.database.get_words(conn, status="rejected")
    write_json("outputs/all_words.json", sorted_word_list)
    write_json("outputs/approved.json", approved_words)
    write_json("outputs/rejected.json", rejected_words)

    conn.close()


if __name__ == "__main__":
    main()
