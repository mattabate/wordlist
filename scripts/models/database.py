import os
import random
import requests
import sqlite3
import time
import yaml

from tqdm import tqdm
from bs4 import BeautifulSoup

from utils.printing import c_red, c_green, c_yellow, c_blue, c_pink, c_end

# -----------------------------
# Load configuration from config.yml
# -----------------------------
CONFIG_FILE = "scripts/config.yml"


def load_config(config_file):
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config(CONFIG_FILE)

# File paths loaded from the "create_db" section.
RAW_WORDLIST_FILE = config["create_db"]["RAW_WORDLIST"]
SCORED_WORDLIST_FILE = config["create_db"]["SCORED_WORDLIST"]
WORDS_APPROVED = config["create_db"]["WORDS_APPROVED"]
WORDS_REJECTED = config["create_db"]["WORDS_REJECTED"]
DATABASE_FILE = config["create_db"].get("DATABASE_FILE", "wordlist.db")


def create_table(conn):
    """
    Creates the 'wordlist' table in the connected SQLite database.
    'answers' and 'status' are defined as NOT NULL.
    """
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS wordlist (
        answers TEXT NOT NULL PRIMARY KEY CHECK(length(answers) BETWEEN 2 AND 40 AND answers = UPPER(answers)),
        clues   TEXT,
        scores  INTEGER CHECK (scores IS NULL OR scores < 100),
        status  TEXT NOT NULL CHECK( status IN ('unchecked','approved','rejected') )
    );
    """
    conn.execute(create_table_sql)
    conn.commit()


def create_indexes(conn):
    """
    Creates indexes on columns to facilitate fast searching.
    """
    conn.execute("CREATE INDEX IF NOT EXISTS idx_answers ON wordlist(answers);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scores ON wordlist(scores);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON wordlist(status);")
    conn.commit()


def print_schema(conn):
    """
    Prints the schema for the 'wordlist' table.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(wordlist);")
    rows = cursor.fetchall()
    print("\nDatabase schema for table 'wordlist':")
    print(
        "{:<5} {:<10} {:<20} {:<8} {:<10} {:<5}".format(
            "cid", "name", "type", "notnull", "dflt_value", "pk"
        )
    )
    print("-" * 60)
    for row in rows:
        cid, name, type_, notnull, dflt_value, pk = row
        print(
            "{:<5} {:<10} {:<20} {:<8} {:<10} {:<5}".format(
                cid, name, type_, notnull, str(dflt_value), pk
            )
        )
    print()


def get_clues_for_word(word: str, db_path: str = DATABASE_FILE) -> str:
    """
    Returns the clues string from the 'wordlist' table for a given word.
    If the word is not found or has no clues, returns None.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Convert the input word to uppercase to match your DB's stored answers
        cursor.execute("SELECT clues FROM wordlist WHERE answers = ?", (word.upper(),))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_words(conn, status=""):
    """
    Fetches words and their clues from the database filtered by status.
    If no status is provided, it fetches all words.
    """
    cur = conn.cursor()
    if status:
        query = "SELECT answers, clues FROM wordlist WHERE status = ?;"
        cur.execute(query, (status,))
    else:
        query = "SELECT answers, clues FROM wordlist;"
        cur.execute(query)

    rows = cur.fetchall()
    return {answer: clues for answer, clues in rows}


_NUM_CLUES = 6


# -----------------------------
# Functions
# -----------------------------
def fetch_clues(word):
    """
    Fetch clues for a word from crosswordtracker.com.
    If no clues are found, returns None.
    """
    url = f"https://crosswordtracker.com/answer/{word.lower()}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CrosswordDBUpdater/1.0; +https://github.com/mattabate/wordlist)"
    }
    params = {}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        code = response.status_code
    except Exception as e:
        tqdm.write(
            f"{c_red}Warning{c_end}: Exception occurred while fetching clues for {word}: {e}"
        )
        code = None

    # If the request was unsuccessful, return None
    if code != 200:
        return None

    # Otherwise, parse the HTML
    time.sleep(random.uniform(0.15, 0.2))  # small delay to be nice to the server
    soup = BeautifulSoup(response.text, "html.parser")
    clue_header = soup.find("h3", string="Referring crossword puzzle clues")
    if clue_header:
        clue_container = clue_header.find_next_sibling("div")
        if clue_container:
            li_items = clue_container.find_all("li")
            if li_items:
                clues_text = "\n".join(
                    [f"- {li.get_text(strip=True)}" for li in li_items[:_NUM_CLUES]]
                )
                return clues_text
    return None
