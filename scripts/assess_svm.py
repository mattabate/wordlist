"""
Assess the trained SVM model on a given set of approved and not approved words.
Computes accuracy and prints to terminal.
"""

import os
import time
import pickle
import random
import yaml
import tqdm

from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics import accuracy_score

import utils.json  # your custom JSON utility
import utils.printing
from models.svm import embed_in_chunks
from create_db import get_clues_for_word

# ------------------------------------------------------------------------------
#  Load Configs
# ------------------------------------------------------------------------------
load_dotenv()  # in case you need environment variables
with open("scripts/config.yml", "r") as file:
    config = yaml.safe_load(file)

WORDS_APPROVED = config["assess_svm"]["WORDS_APPROVED"]
WORDS_REJECTED = config["assess_svm"]["WORDS_REJECTED"]
MODEL_FILE_PATH = config["assess_svm"]["MODEL_FILE"]  # SVM model (pickle file)
EMB_MODEL_NAME = os.getenv("EMB_MODL", "text-embedding-3-small")  # fallback

# ------------------------------------------------------------------------------
#  Create OpenAI client
# ------------------------------------------------------------------------------
client = OpenAI()


# ------------------------------------------------------------------------------
#  Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 1) Load Approved & Rejected Wordlists
    approved_words = utils.json.load_json(WORDS_APPROVED)
    rejected_words = utils.json.load_json(WORDS_REJECTED)

    print(
        f"{utils.printing.c_yellow}Assessing SVM Model:{utils.printing.c_end} {MODEL_FILE_PATH}"
    )
    print(
        f"{utils.printing.c_yellow}Total Approved Words:{utils.printing.c_end} {len(approved_words)}"
    )
    print(
        f"{utils.printing.c_yellow}Total Rejected Words:{utils.printing.c_end} {len(rejected_words)}"
    )
    # 2) Load Trained SVM Model
    with open(MODEL_FILE_PATH, "rb") as f:
        svm_model = pickle.load(f)

    _max_words = 3000  # limit to 1000 words for speed
    print(f"{utils.printing.c_pink}max for study:{utils.printing.c_end} {_max_words}")
    # 3) Embed Approved & Rejected Words
    random.shuffle(approved_words)
    random.shuffle(rejected_words)

    approved_words = approved_words[: min(_max_words, len(approved_words))]
    rejected_words = rejected_words[: min(_max_words, len(rejected_words))]

    approved_words_w_clues = {
        w: get_clues_for_word(w, "wordlist.db") for w in approved_words
    }
    rejected_words_w_clues = {
        w: get_clues_for_word(w, "wordlist.db") for w in rejected_words
    }

    approved_embeddings = embed_in_chunks(approved_words_w_clues)
    rejected_embeddings = embed_in_chunks(rejected_words_w_clues)

    # 4) Build label arrays (1 = approved, 0 = rejected)
    y_true_approved = [1] * len(approved_words)
    y_true_rejected = [0] * len(rejected_words)
    y_true = y_true_approved + y_true_rejected

    # 5) Predict
    # Concatenate embeddings for all words (approved then rejected)
    all_embeddings = approved_embeddings + rejected_embeddings
    y_pred = svm_model.predict(all_embeddings)

    # 6) Compute accuracy
    accuracy = accuracy_score(y_true, y_pred)
    print(f"\nModel Accuracy on Provided Wordlists: {accuracy * 100:.2f}%")
