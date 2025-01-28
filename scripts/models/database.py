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


def get_words_and_clues(conn, status=""):
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


def get_words(conn, status=""):
    """
    Fetches words and their clues from the database filtered by status.
    If no status is provided, it fetches all words.
    """
    cur = conn.cursor()
    if status:
        query = "SELECT answers FROM wordlist WHERE status = ?;"
        cur.execute(query, (status,))
    else:
        query = "SELECT answers FROM wordlist;"
        cur.execute(query)

    rows = cur.fetchall()
    return [answer for answer, in rows]


_NUM_CLUES = 6


# -----------------------------
# Functions
# -----------------------------
def fetch_clues(word) -> str | None:
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


def update_score(conn, word: str, score: int) -> int:
    """
    Updates the score for a given word in the 'wordlist' table.
    Returns the number of rows that were updated (usually 0 or 1).
    """
    word = word.upper()  # Ensure consistency with the DB
    cursor = conn.cursor()
    cursor.execute("UPDATE wordlist SET scores = ? WHERE answers = ?", (score, word))
    conn.commit()
    return cursor.rowcount


def add_source(
    conn: sqlite3.Connection, name: str, source_link: str, file_path: str
) -> int:
    """
    Attempts to add a new source to the 'sources' table, returning the row's primary key in three cases:
      1) If no row matches exactly (name, source, file), a new row is inserted and the new ID returned.
      2) If an existing row already matches exactly (name, source, file), return that row's ID (no insert).
      3) If there's a uniqueness conflict but not an exact match, raise an error.

    :param conn: Active sqlite3.Connection object
    :param name:    The descriptive name of the source (<= 50 chars, unique)
    :param source_link: The link or identifier for the source (<= 50 chars, unique)
    :param file_path:   The local file path for this source (<= 50 chars, unique)
    :return: An int representing the ID of the row in 'sources'
    :raises ValueError: If a uniqueness conflict is triggered (partial match).
    """

    # STEP 1: Check if an exact match already exists
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM sources
        WHERE name = ?
          AND source = ?
          AND file = ?
        """,
        (name, source_link, file_path),
    )
    row = cursor.fetchone()
    if row:
        # Scenario #3: Exact match found
        existing_id = row[0]
        print(f"Source already exists with ID={existing_id}. Returning existing ID.")
        return existing_id

    # STEP 2: Attempt insert for a brand-new source
    try:
        cursor.execute(
            """
            INSERT INTO sources (name, source, file)
            VALUES (?, ?, ?)
            """,
            (name, source_link, file_path),
        )
        new_id = cursor.lastrowid
        conn.commit()
        # Scenario #1: Insert succeeded, so return the new source ID
        return new_id

    except sqlite3.IntegrityError as e:
        # STEP 3: We know the row doesn't exactly match, because we checked above.
        # So this must be a partial conflict -> Raise an error
        raise ValueError(
            "Uniqueness conflict: a row with one of these fields already exists, but does not match all fields."
        ) from e


def create_source_word(
    conn: sqlite3.Connection, source_id: int, word_id: str, score: int = None
):
    """
    Inserts or updates a row in 'source_word' that links a source to a word.

    Table schema (recap):
        CREATE TABLE IF NOT EXISTS source_word (
            source_id INTEGER NOT NULL,
            word_id   TEXT NOT NULL,
            score     INTEGER,
            FOREIGN KEY(source_id) REFERENCES sources(id)
                ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY(word_id) REFERENCES wordlist(answers)
                ON UPDATE CASCADE ON DELETE CASCADE,
            PRIMARY KEY (source_id, word_id)
        );

    Behavior:
      1. If (source_id, word_id, score) already exists exactly, prints a message and does nothing more.
      2. If (source_id, word_id) exists but has a different score, updates the row's score.
      3. If no row with (source_id, word_id) exists, inserts a new row.

    :param conn:      An active sqlite3.Connection object
    :param source_id: The 'id' from the 'sources' table
    :param word_id:   The 'answers' text PK from the 'wordlist' table
    :param score:     An optional score for this specific source/word relationship
    :return: None
    """
    cursor = conn.cursor()

    # 1) Check if there's already a row with the same (source_id, word_id)
    cursor.execute(
        """
        SELECT score
          FROM source_word
         WHERE source_id = ?
           AND word_id = ?
    """,
        (source_id, word_id),
    )
    row = cursor.fetchone()

    if row is not None:
        existing_score = row[0]
        # If the row already has the exact same score, do nothing
        if existing_score == score:
            print(
                f"[INFO] source_word entry (source_id={source_id}, word_id='{word_id}') "
                "already exists with the same score. Nothing to do."
            )
        else:
            # 2) (source_id, word_id) exists but different score -> update
            cursor.execute(
                """
                UPDATE source_word
                   SET score = ?
                 WHERE source_id = ?
                   AND word_id = ?
            """,
                (score, source_id, word_id),
            )
            print(
                f"[INFO] Updated source_word (source_id={source_id}, word_id='{word_id}') "
                f"from score={existing_score} to score={score}."
            )
        conn.commit()
        return
    else:
        # 3) No row exists for (source_id, word_id) -> insert a new record
        try:
            cursor.execute(
                """
                INSERT INTO source_word (source_id, word_id, score)
                VALUES (?, ?, ?)
            """,
                (source_id, word_id, score),
            )
            conn.commit()
            print(
                f"[INFO] Created new source_word (source_id={source_id}, word_id='{word_id}', score={score})."
            )
        except sqlite3.IntegrityError as e:
            # Raise a more descriptive error if something unexpected happens (e.g., invalid FK reference).
            raise ValueError(
                f"Failed to insert into source_word: source_id={source_id}, word_id='{word_id}', score={score}. "
                "Likely a foreign key or uniqueness constraint issue."
            ) from e


def add_word(conn: sqlite3.Connection, word: str):
    """
    Adds a word if not present, then returns the SQLite internal rowid.
    """
    word_upper = word.upper()
    cursor = conn.cursor()

    # Check if the word already exists
    cursor.execute("SELECT rowid FROM wordlist WHERE answers = ?", (word_upper,))
    row = cursor.fetchone()
    if row is not None:
        tqdm.write(
            f"{c_yellow}Warning:{c_end} Word {word_upper}already exists in the database. Skipping"
        )
        return

    # Insert
    cursor.execute(
        """
        INSERT INTO wordlist (answers, clues, scores, status)
        VALUES (?, ?, ?, ?)
    """,
        (word_upper, fetch_clues(word=word_upper), None, "unchecked"),
    )
    conn.commit()
