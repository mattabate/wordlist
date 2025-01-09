"""
Assess the trained SVM model on a given set of approved and not approved words.
Computes accuracy and prints to terminal.
"""

import os
import time
import pickle
import yaml
import tqdm

from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics import accuracy_score

import utils.json  # your custom JSON utility

# ------------------------------------------------------------------------------
#  Load Configs
# ------------------------------------------------------------------------------
load_dotenv()  # in case you need environment variables
with open("scripts/config.yml", "r") as file:
    config = yaml.safe_load(file)

WORDS_APPROVED = config["assess_svm"]["WORDS_APPROVED"]
WORDS_REJECTED = config["assess_svm"]["WORDS_REJECTED"]
MODEL_FILE_PATH = config["assess_svm"]["MODEL_FILE"]  # SVM model (pickle file)
TRAIN_EMB_PREF = config["assess_svm"]["PREFIX_FOR_EMBEDDING"]
EMB_MODEL_NAME = os.getenv("EMB_MODL", "text-embedding-3-small")  # fallback

# ------------------------------------------------------------------------------
#  Create OpenAI client
# ------------------------------------------------------------------------------
client = OpenAI()


# ------------------------------------------------------------------------------
#  Embedding Helper
# ------------------------------------------------------------------------------
def embed_in_chunks(words, chunk_size=1500):
    """
    Embeds a list of words (with training prefix) in chunks to avoid rate limits.
    Returns a list of embedding vectors.
    """
    vectors = []
    for i in tqdm.tqdm(range(0, len(words), chunk_size), desc="Embedding"):
        batch = words[i : i + chunk_size]
        # Prepend training prefix
        batch_prefixed = [TRAIN_EMB_PREF + w for w in batch]

        response = client.embeddings.create(
            input=batch_prefixed, model=EMB_MODEL_NAME
        ).data
        batch_vectors = [item.embedding for item in response]
        vectors.extend(batch_vectors)

        time.sleep(0.5)  # small pause to avoid hitting rate limits
    return vectors


# ------------------------------------------------------------------------------
#  Main
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 1) Load Approved & Rejected Wordlists
    approved_words = utils.json.load_json(WORDS_APPROVED)
    rejected_words = utils.json.load_json(WORDS_REJECTED)

    # 2) Load Trained SVM Model
    with open(MODEL_FILE_PATH, "rb") as f:
        svm_model = pickle.load(f)

    # 3) Embed Approved & Rejected Words
    approved_embeddings = embed_in_chunks(approved_words)
    rejected_embeddings = embed_in_chunks(rejected_words)

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
