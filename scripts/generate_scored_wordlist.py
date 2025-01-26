"""score the words in the wordlist using a pretrained SVM model"""

import json
import sqlite3
import tqdm
import yaml

import models.database
import utils.printing

from models.svm import infer

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    DATABASE_FILE = "wordlist.db"
    RAW_WORDLIST = config["generate_scored_wordlist"]["RAW_WORDLIST"]
    SCORED_WORDLIST = config["generate_scored_wordlist"]["SCORED_WORDLIST"]
    SORTED_WORDLIST = config["generate_scored_wordlist"]["SORTED_WORDLIST"]
    SCORED_WORDLIST_TXT = config["generate_scored_wordlist"]["SCORED_WORDLIST_TXT"]

if __name__ == "__main__":
    with open(RAW_WORDLIST) as file:
        data = json.load(file)

    print(
        f"{utils.printing.c_yellow}Number of words:{utils.printing.c_end} {len(data)}"
    )

    model_output = infer(data)

    # get max and min scores
    max_score = max(model_output, key=lambda x: x[1])
    min_score = min(model_output, key=lambda x: x[1])

    # normalize so they are 0 - 50
    matt_scores = {
        w: int((s - min_score[1]) / (max_score[1] - min_score[1]) * 50)
        for w, s in model_output
    }

    with open(SCORED_WORDLIST, "w") as file:
        json.dump(matt_scores, file, indent=4)

    with open(SORTED_WORDLIST, "w") as file:
        json.dump([w for w, _ in model_output], file, indent=4)

    with open(SCORED_WORDLIST_TXT, "w") as file:
        for word, score in matt_scores.items():
            file.write(f"{word};{score}\n")

    # update scores in db

    conn = sqlite3.connect(DATABASE_FILE)
    try:
        words = models.database.get_words(conn, status="")
        for word in tqdm.tqdm(words):
            if word not in matt_scores:
                tqdm.tqdm.write(
                    f"Word {utils.printing.c_pink}{word}{utils.printing.c_end} not in wordlist. Setting score to 0."
                )
                models.database.update_score(conn, word, 0)
            else:
                tqdm.tqdm.write(
                    f"Updating score for {utils.printing.c_green}{word}{utils.printing.c_end} to {utils.printing.c_green}{matt_scores[word]}{utils.printing.c_end}"
                )
                models.database.update_score(conn, word, matt_scores[word])

    except Exception as e:
        print(f"{utils.printing.c_red}Error:{utils.printing.c_end} {e}")
        conn.rollback()
    finally:
        conn.close()
