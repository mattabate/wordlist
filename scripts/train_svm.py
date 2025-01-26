"""score the words in the wordlist using a pretrained SVM model"""

import os
import sqlite3
import yaml

from utils.printing import c_red, c_end
from models.svm import train_svm
from models.database import get_words


def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG_FILE = "scripts/config.yml"

config = load_config(CONFIG_FILE)

DATABASE_FILE = config["create_db"].get("DATABASE_FILE", "wordlist.db")

if __name__ == "__main__":
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        approved = get_words(conn=conn, status="approved")
        rejected = get_words(conn=conn, status="rejected")

    except Exception as e:
        print(f"{c_red}Error:{c_end} {e}")
        conn.rollback()
    finally:
        conn.close()

    train_svm(approved, rejected)
