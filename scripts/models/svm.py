import os
import pickle
import time
import tqdm
import yaml

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
EMB_MODL = os.getenv("EMB_MODL")

# EMB_PREF should actually come from the config file yaml
with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    EMB_PREF = config["PREFIX_FOR_EMBEDDING"]
    PKL_MODL = config["MODEL_FILE"]

client = OpenAI()

with open(PKL_MODL, "rb") as file:
    clf = pickle.load(file)


def infer(words: list[str]) -> list[tuple[str, float]]:
    """Return a sorted list of tuples of words and their corresponding scores, from most assumed good to most assumed bad."""
    _step = 1000  # Smaller chunk size for better progress tracking
    words_considered = [EMB_PREF + w for w in words]
    word_scores = []

    for i in tqdm.tqdm(range(0, len(words_considered), _step)):
        # Process a batch of words
        batch_words = words_considered[i : i + _step]
        good_vectors = client.embeddings.create(input=batch_words, model=EMB_MODL).data
        batch_out = [x.embedding for x in good_vectors]

        # Compute decision function scores for the current batch
        batch_scores = clf.decision_function(batch_out)

        # Append the scores for the batch
        word_scores += [
            (words[j], float(batch_scores[j - i]))
            for j in range(i, min(i + _step, len(words)))
        ]

        # Pause to avoid overloading the client
        time.sleep(0.5)

    # Sort words from most assumed bad to most assumed good
    word_scores_sorted = sorted(word_scores, key=lambda x: x[1], reverse=True)
    return word_scores_sorted
