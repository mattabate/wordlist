#!/usr/bin/env python3
"""
Migration script to add the following tables to the database:
1) model
2) word_model_score

Usage:
  python add_model_tables.py
"""

import sqlite3
import os

DATABASE_FILE = "wordlist.db"


def create_tables(conn):
    """
    Creates the 'model' and 'word_model_score' tables if they don't exist.
    """
    cur = conn.cursor()

    # 1) model table
    #    - id (int primary key)
    #    - pkl_file_name (str)
    #    - time_trained (date) --> stored as TEXT in SQLite
    #    - training_score (float)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS model (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pkl_file_name TEXT NOT NULL,
            time_trained TEXT NOT NULL,
            training_score REAL NOT NULL
        );
    """
    )

    # 2) word_model_score table
    #    - word (str) [foreign key to wordlist.answers]
    #    - model (int) [foreign key to model.id]
    #    - score (float)
    #    - (word, model) is a unique pair, serving as the primary key
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS word_model_score (
            word TEXT NOT NULL,
            model INTEGER NOT NULL,
            score REAL NOT NULL,
            PRIMARY KEY(word, model),
            FOREIGN KEY(word) REFERENCES wordlist(answers),
            FOREIGN KEY(model) REFERENCES model(id)
        );
    """
    )

    conn.commit()


def main():
    if not os.path.exists(DATABASE_FILE):
        print(f"Database file '{DATABASE_FILE}' not found.")
        return

    conn = sqlite3.connect(DATABASE_FILE)
    try:
        create_tables(conn)
        print("Successfully created/verified 'model' and 'word_model_score' tables.")
    except Exception as e:
        print(f"Error creating new tables: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
