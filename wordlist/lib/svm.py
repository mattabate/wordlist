import json
import os
import pickle
import time
import tqdm
import yaml

from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Tuple

from sklearn.svm import SVC
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from wordlist.lib.database import get_clues_for_word
from wordlist.utils.printing import c_blue, c_end

# ------------------------------------------------------------------------------
#  Initialization / Config
# ------------------------------------------------------------------------------
load_dotenv(dotenv_path=".env")

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
EMB_MODL = os.getenv("EMB_MODL")

# Create OpenAI client (adjust as needed)
client = OpenAI()

with open("search_config.yml", "r") as file:
    config = yaml.safe_load(file)

tt_split = config["ratio_test"]  # 0.2 means 20% test set
tolerance = config["tolerance"]
max_iter = config["max_iter"]

SEARCH_PARAM = {
    "svm__kernel": config["svm_parameters"]["kernel"],
    "svm__degree": config["svm_parameters"][
        "degree"
    ],  # Including degree 5 for more nonlinearity
    "svm__gamma": config["svm_parameters"]["gamma"],
    "svm__coef0": config["svm_parameters"]["coef0"],  # Independent term
    "svm__C": config["svm_parameters"][
        "C"
    ],  # Regularization parameter; higher C allows more overfitting
}
_cv = config["num_folds"]

pipeline = Pipeline(
    [
        ("scaler", StandardScaler()),
        ("svm", SVC(tol=tolerance, max_iter=max_iter)),
    ]
)


# ------------------------------------------------------------------------------
#  Inference Function
# ------------------------------------------------------------------------------
def infer(PKL_MODL, words: List[str]) -> List[Tuple[str, float]]:
    """
    Return a sorted list of (word, score) tuples, from most assumed good (score high)
    to most assumed bad (score low).
    """
    chunk_size = 1500
    words_considered = [add_prefix(w, get_clues_for_word(w)) for w in words]
    word_scores = []
    with open(PKL_MODL, "rb") as file:
        clf = pickle.load(file)

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


def add_prefix(word: str, clues: str = "") -> str:

    prompt = (
        "I am making a wordlist for crossword puzzle constructors. "
        + f"Do you think you would be able to guess this word '{word}' if it was used in a puzzle? "
        + f"Respond NO if you think '{word}' is too obscure and YES if you think '{word}' is common."
    )
    if clues:
        prompt = prompt + "\n\n" + "Here are some possible clues: " + "\n" + clues
    return prompt


# ------------------------------------------------------------------------------
#  Embedding helper
# ------------------------------------------------------------------------------
def get_embeddings(words_batch_dict: dict[str, str]) -> List[List[float]]:
    """
    Embed a batch of words using the TRAIN_EMB_PREF prefix.
    Returns the list of embedding vectors.
    """

    words_with_prefix = [add_prefix(w, c) for w, c in words_batch_dict.items()]
    response = client.embeddings.create(input=words_with_prefix, model=EMB_MODL).data
    vectors = [item.embedding for item in response]
    return vectors


# ------------------------------------------------------------------------------
#  1) Make Train/Test Split
# ------------------------------------------------------------------------------
def make_train_test_split(
    approved_words: List[str],
    not_approved_words: List[str],
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[List[str], List[str], List[int], List[int]]:
    """
    Combine approved and not-approved words, create labels, then split into train/test.
    Returns (X_train_words, X_test_words, y_train, y_test).
    """
    all_words = approved_words + not_approved_words
    labels = [1] * len(approved_words) + [0] * len(not_approved_words)

    X_train_words, X_test_words, y_train, y_test = train_test_split(
        all_words,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )
    return X_train_words, X_test_words, y_train, y_test


# ------------------------------------------------------------------------------
#  2) Embed data in chunks
# ------------------------------------------------------------------------------
def embed_in_chunks(
    words_clues_dict: dict[str, str], chunk_size: int = 1500
) -> List[List[float]]:
    """
    Embed a list of words in manageable chunks (to avoid rate limits).
    Uses the 'get_embeddings' helper under the hood.
    """
    words = list(words_clues_dict.keys())
    vectors = []
    for i in tqdm.tqdm(range(0, len(words), chunk_size)):
        batch = words[i : i + chunk_size]
        batch_dict = {word: words_clues_dict[word] for word in batch}
        batch_vectors = get_embeddings(batch_dict)
        vectors.extend(batch_vectors)
        time.sleep(0.5)  # small pause to avoid rate-limit issues
    return vectors


# ------------------------------------------------------------------------------
#  3) Train Model (GridSearch)
# ------------------------------------------------------------------------------
def train_model(
    X_train_vectors: List[List[float]], y_train: List[int]
) -> Tuple[SVC, dict]:
    """
    Given training vectors and labels, perform a GridSearchCV to find best SVM hyperparams.
    Returns the best estimator.
    """
    print("\nStarting SVM Grid Search (this may take a while)...")
    train_start_time = time.time()

    # Use the pipeline defined earlier (with StandardScaler and SVC)
    grid_search = GridSearchCV(
        pipeline,
        param_grid=SEARCH_PARAM,
        cv=_cv,
        scoring="accuracy",
        verbose=4,
        n_jobs=1,
    )

    grid_search.fit(X_train_vectors, y_train)

    train_end_time = time.time()
    elapsed_time = train_end_time - train_start_time

    print(f"\nGrid Search completed in {elapsed_time:.2f} seconds.")
    print("Best Parameters:", grid_search.best_params_)
    print(
        f"Best Cross-Validation Accuracy (Train Set): {grid_search.best_score_ * 100:.2f}%"
    )

    best_clf = grid_search.best_estimator_

    log_output = {
        "best_parameters": grid_search.best_params_,
        "search_time_seconds": int(elapsed_time),
    }
    return best_clf, log_output


# ------------------------------------------------------------------------------
#  4) Evaluate Model
# ------------------------------------------------------------------------------
def evaluate_model(
    model: SVC, X_test_vectors: List[List[float]], y_test: List[int]
) -> float:
    """
    Predict on test vectors, print and return the accuracy.
    """
    y_pred = model.predict(X_test_vectors)
    test_acc = accuracy_score(y_test, y_pred)
    print(f"\nFinal Test Accuracy with best parameters: {test_acc * 100:.2f}%")
    return test_acc


# ------------------------------------------------------------------------------
#  5) Master Train Function
# ------------------------------------------------------------------------------
def train_svm(
    set_1_words_clues: dict[str, str], set_2_words_clues: dict[str, str]
) -> tuple[SVC, dict]:
    """
    Master function that:
    1) Makes train/test sets
    2) Embeds train/test
    3) Trains an SVM via grid search
    4) Evaluates the best model
    5) Saves the model
    """

    _train_limit = 10000000

    set_1_words: list[str] = list(set_1_words_clues.keys())
    set_2_words: list[str] = list(set_2_words_clues.keys())
    set_1_words = set_1_words[
        : min(_train_limit, len(set_1_words_clues), len(set_2_words_clues))
    ]
    set_2_words = set_2_words[
        : min(_train_limit, len(set_1_words_clues), len(set_2_words_clues))
    ]

    # -- 1) Split
    X_train_words, X_test_words, y_train, y_test = make_train_test_split(
        set_1_words, set_2_words, test_size=tt_split
    )

    train_dict = {}
    for word in X_train_words:
        if word in set_1_words_clues:
            train_dict[word] = set_1_words_clues[word]
        else:
            train_dict[word] = set_2_words_clues[word]

    # -- 2) Embed training and test sets
    print("Embedding train set...")
    X_train_vectors = embed_in_chunks(train_dict)

    test_dict = {}
    for word in X_test_words:
        if word in set_1_words_clues:
            test_dict[word] = set_1_words_clues[word]
        else:
            test_dict[word] = set_2_words_clues[word]

    # -- 3) Train (grid search)
    tqdm.tqdm.write(c_blue + "Search Config:" + c_end)
    tqdm.tqdm.write(json.dumps(config, indent=2))

    best_clf, log_output = train_model(X_train_vectors, y_train)

    print("Embedding test set...")
    X_test_vectors = embed_in_chunks(test_dict)
    score = evaluate_model(best_clf, X_test_vectors, y_test)

    config["best_parameters"] = log_output["best_parameters"]
    config["search_time_seconds"] = log_output["search_time_seconds"]
    config["test_score"] = score
    return best_clf, config
