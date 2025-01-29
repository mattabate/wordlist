"""score the words in the wordlist using a pretrained SVM model"""

import datetime
import os
import pickle
import sqlite3
import yaml

from utils.printing import c_red, c_end
from models.svm import train_svm
from models.database import get_words_and_clues, add_model


def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG_FILE = "scripts/config.yml"

config = load_config(CONFIG_FILE)
DATABASE_FILE = config["db_file"]

if __name__ == "__main__":
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        approved = get_words_and_clues(conn=conn, status="approved")
        rejected = get_words_and_clues(conn=conn, status="rejected")

    except Exception as e:
        print(f"{c_red}Error:{c_end} {e}")
        conn.rollback()
    finally:
        conn.close()

    best_clf, score = train_svm(approved, rejected)

    # current daretime string format 2025-01-28 05:29:09
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DATABASE_FILE)
    success = True
    try:
        model_id = add_model(conn, score, date)
    except Exception as e:
        print(f"{c_red}Error:{c_end} {e}")
        conn.rollback()
        success = False
    finally:
        conn.close()

    if success:
        with open(f"scripts/models/models/{model_id}.pkl", "wb") as f:
            pickle.dump(best_clf, f)

        print(f"SVM model saved as: {model_id}.pkl")
