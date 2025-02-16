"""score the words in the wordlist using a pretrained SVM model"""

import datetime
import json
import os
import pickle
import sqlite3

from dotenv import load_dotenv

from wordlist.lib.database import get_words_and_clues, add_model
from wordlist.lib.svm import train_svm
from wordlist.utils.printing import c_red, c_end, c_yellow


load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
DATABASE_FILE = os.getenv("SQLITE_DB_FILE")

if not os.path.exists("models"):
    os.makedirs("models")

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

    if not approved or not rejected:
        print("Can't train svm unil sorted")
        exit()
    best_clf, log_output = train_svm(approved, rejected)

    out_in = input(c_yellow + "You you like to save model? (N to reject)" + c_end)
    if out_in == "N":
        exit()
    # current daretime string format 2025-01-28 05:29:09
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DATABASE_FILE)
    success = True
    try:
        score = log_output["score"]
        pkl_file_name = add_model(
            conn, score, date, log_output["duration"], json.dumps(log_output)
        )
    except Exception as e:
        print(f"{c_red}Error:{c_end} {e}")
        conn.rollback()
        success = False
    finally:
        conn.close()

    if success:
        with open(pkl_file_name, "wb") as f:
            pickle.dump(best_clf, f)

        print(f"SVM model saved as: {pkl_file_name}")
