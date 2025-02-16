import os
import random
import requests
import sqlite3
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

from wordlist.utils.printing import c_red, c_green, c_yellow, c_end

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
DATABASE_FILE = os.getenv("SQLITE_DB_FILE")


def get_clues_for_word(word: str, db_path: str = DATABASE_FILE) -> str:
    """
    Returns the clues string from the 'words' table for a given word.
    If the word is not found or has no clues, returns None.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Convert the input word to uppercase to match your DB's stored word
        cursor.execute("SELECT clues FROM words WHERE word = ?", (word.upper(),))
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
        query = "SELECT word, clues FROM words WHERE status = ?;"
        cur.execute(query, (status,))
    else:
        query = "SELECT word, clues FROM words;"
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
        query = "SELECT word FROM words WHERE status = ?;"
        cur.execute(query, (status,))
    else:
        query = "SELECT word FROM words;"
        cur.execute(query)

    rows = cur.fetchall()
    return [answer for answer, in rows]


def sort_words_by_score(
    conn: sqlite3.Connection, words: list[str], model_id: int, order: str = "desc"
) -> list[str]:
    """
    Sorts a list of words by their scores for a given model ID.
    The scores are fetched from the 'word_model_score' table in the database.

    :param conn: An active sqlite3.Connection object.
    :param words: A list of words to sort.
    :param model_id: The ID of the model to use for scoring.
    :param order: The order to sort the words in ('asc' or 'desc').

    :return: A list of words sorted by their scores for the given model ID.
    """
    cur = conn.cursor()

    # Fetch the scores for the given model ID
    cur.execute(
        """
        SELECT word, score
        FROM word_model_score
        WHERE model = ?
        AND word IN ({})
        """.format(
            ", ".join("?" for _ in words)
        ),
        (model_id, *words),
    )
    scores = dict(cur.fetchall())

    # Sort the words by their scores
    return sorted(words, key=lambda w: scores.get(w, 0), reverse=order == "desc")


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


def update_clues_for_word(conn: sqlite3.Connection, word: str) -> None:
    """
    Given a word, fetch its clues from an external API (fetch_clues)
    and, if successful, update both the 'clues' and 'clues_last_updated'
    fields in the 'words' table.
    """
    c = fetch_clues(word)
    if c is not None and c.strip():  # only update if clues is not empty
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE words
            SET clues = ?,
                clues_last_updated = datetime('now')
            WHERE word = ?
            """,
            (c, word.upper()),
        )
        conn.commit()
        return True
    else:
        # update date anyway
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE words
            SET clues_last_updated = datetime('now')
            WHERE word = ?
            """,
            (word.upper(),),
        )
        conn.commit()
        return False


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
            FOREIGN KEY(word_id) REFERENCES words(word)
                ON UPDATE CASCADE ON DELETE CASCADE,
            PRIMARY KEY (source_id, word_id)
        );

    Behavior:
      1. If (source_id, word_id, score) already exists exactly, prints a message and does nothing more.
      2. If (source_id, word_id) exists but has a different score, updates the row's score.
      3. If no row with (source_id, word_id) exists, inserts a new row.

    :param conn:      An active sqlite3.Connection object
    :param source_id: The 'id' from the 'sources' table
    :param word_id:   The 'word' text PK from the 'words' table
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


def add_word(conn: sqlite3.Connection, word: str, clues: str) -> None:
    """
    Adds a word if not present, then returns the SQLite internal rowid.
    """
    cursor = conn.cursor()

    # Check if the word already exists
    cursor.execute("SELECT rowid FROM words WHERE word = ?", (word,))
    row = cursor.fetchone()
    if row is not None:
        tqdm.write(
            f"{c_yellow}Warning:{c_end} Word {word}already exists in the database. Skipping"
        )
        return

    # Insert
    cursor.execute(
        """
        INSERT INTO words (word, time_added, clues, clues_last_updated, status, status_last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            word,
            time.strftime("%Y-%m-%d %H:%M:%S"),
            clues,  # begining of tim
            time.strftime("%Y-%m-%d %H:%M:%S"),
            "unchecked",
            time.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()


def add_model(
    conn, time_trained: str, training_score: float, training_duration: int, meta: str
) -> int:
    """
    Inserts a new model row into the 'model' table, then updates its pkl_file_name
    to match the newly assigned model ID.

    :param conn: An active sqlite3.Connection object.
    :param datetime_trained: A string representing the training time (ISO 8601 recommended).
    :param training_score: The model's training performance score as a float.

    :return: The newly assigned 'id' from the 'model' table.
    """
    cur = conn.cursor()

    # 1. Insert a placeholder row (autoincrement assigns an ID)
    cur.execute(
        """
        INSERT INTO model (pkl_file_name, training_score, datetime_trained, training_duration, meta)
        VALUES ('placeholder', ?, ?, ?, ?)
        """,
        (training_score, time_trained, training_duration, meta),
    )
    new_id = cur.lastrowid  # the newly assigned primary key

    # 2. Update the just-inserted row so pkl_file_name matches new_id
    #    For example, you can store it as "123.pkl" or just "123"
    pkl_file_name = f"models/{new_id}.pkl"
    cur.execute(
        """
        UPDATE model
        SET pkl_file_name = ?
        WHERE id = ?
        """,
        (pkl_file_name, new_id),
    )

    conn.commit()
    return pkl_file_name


def add_word_model_score(
    conn: sqlite3.Connection, word: str, model_id: int, score: float
) -> None:
    """
    Inserts a new (word, model, score) row into the word_model_score table.

    :param conn: A live sqlite3.Connection object.
    :param model_id: The integer ID of the model (foreign key to model.id).
    :param word: The word to be scored (foreign key to words.word).
    :param score: The floating-point score for this (word, model) pair.

    Note: Raises sqlite3.IntegrityError if (word, model) already exists,
    or if 'word'/'model' does not exist in their respective tables (if FK constraints are on).
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO word_model_score (word, model, score)
            VALUES (?, ?, ?)
            """,
            (word.upper(), model_id, score),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        # Handle or re-raise integrity errors (duplicate primary key, foreign key missing, etc.)
        raise e


def update_word_status(conn: sqlite3.Connection, word: str, new_status: str) -> None:
    """
    Updates the status of a given word in the 'words' table.

    :param conn: An active sqlite3.Connection object.
    :param word: The word whose status needs to be updated.
    :param new_status: The new status to set for the word (e.g., 'approved', 'rejected', 'unchecked').

    :raises ValueError: If the word does not exist in the database.
    :raises sqlite3.Error: If a database error occurs during the operation.
    """
    word_upper = word.upper()
    cur = conn.cursor()

    try:
        # Check if the word exists
        cur.execute("SELECT status FROM words WHERE word = ?", (word_upper,))
        row = cur.fetchone()

        if row is None:
            tqdm.write(
                f"{c_red}Error:{c_end} Word '{word_upper}' does not exist in the database."
            )
            raise ValueError(f"Word '{word_upper}' not found in the database.")

        current_status = row[0]

        # Update the status only if it's different
        if current_status != new_status:
            cur.execute(
                """
                UPDATE words 
                SET status = ?,
                    status_last_updated = datetime('now')
                WHERE word = ?
                """,
                (new_status, word_upper),
            )
            conn.commit()
            tqdm.write(
                f"{c_green}Success:{c_end} Updated status of '{word_upper}' from '{current_status}' to '{new_status}'."
            )
            return True
        else:
            tqdm.write(
                f"{c_yellow}Notice:{c_end} The word '{word_upper}' already has status '{new_status}'. No update needed."
            )
            return False

    except sqlite3.Error as e:
        tqdm.write(f"{c_red}SQLite Error:{c_end} {e}")
        conn.rollback()
        raise


def get_model_pkl_file_name(conn: sqlite3.Connection, model_id: int) -> str:
    """
    Retrieves the pkl_file_name for a given model ID from the 'model' table.

    :param conn: An active sqlite3.Connection object.
    :param model_id: The ID of the model to retrieve.

    :return: The pkl_file_name associated with the given model ID.

    :raises ValueError: If the model ID does not exist in the table.
    :raises sqlite3.Error: If a database error occurs.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT pkl_file_name
            FROM model
            WHERE id = ?
            """,
            (model_id,),
        )
        result = cur.fetchone()
        if result:
            return result[0]
        else:
            raise ValueError(f"Model with ID {model_id} does not exist.")
    except sqlite3.Error as e:
        # Optionally, you can log the error or handle it as needed
        raise sqlite3.Error(f"An error occurred while accessing the database: {e}")
