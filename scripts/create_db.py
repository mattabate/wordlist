import sqlite3
import os

from wordlist.utils.printing import c_yellow, c_end


def create_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS source_word (
            source_id INTEGER NOT NULL,
            word_id TEXT NOT NULL,
            score INTEGER,
            FOREIGN KEY(source_id) REFERENCES sources(id)
                ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY(word_id) REFERENCES words(word)
                ON UPDATE CASCADE ON DELETE CASCADE,
            PRIMARY KEY (source_id, word_id)
        );
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE CHECK(LENGTH(name) <= 200),
            source TEXT NOT NULL UNIQUE CHECK(LENGTH(source) <= 200),
            file TEXT NOT NULL UNIQUE CHECK(LENGTH(file) <= 200),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS word_model_score (
            word TEXT NOT NULL,
            model INTEGER NOT NULL,
            score REAL NOT NULL,
            PRIMARY KEY (word, model),
            FOREIGN KEY(word) REFERENCES words(word),
            FOREIGN KEY(model) REFERENCES model(id)
        );
    """
    )

    # Updated words table: clues information is now removed
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS words (
            word TEXT PRIMARY KEY NOT NULL,
            time_added TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('approved', 'rejected', 'unchecked')),
            status_last_updated TEXT NOT NULL
        );
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model (
            id INTEGER PRIMARY KEY,
            pkl_file_name TEXT NOT NULL,
            training_score REAL NOT NULL,
            datetime_trained TEXT NOT NULL,
            training_duration INT,
            meta TEXT
        );
    """
    )

    # New table for storing unique clues
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clue TEXT UNIQUE,
            last_seen TEXT
        );
    """
    )

    # New table for storing word-clue relationships
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clue_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            clue_id INTEGER,
            source TEXT,
            FOREIGN KEY(word) REFERENCES words(word),
            FOREIGN KEY(clue_id) REFERENCES clues(id)
        );
    """
    )


def main():
    db_filename = "wordlist.db"
    if os.path.exists(db_filename):
        print(f"{c_yellow}Warning{c_end}: The file '{db_filename}' already exists.")
        print("Please delete the existing database file before proceeding.")
        return

    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    create_tables(cursor)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
