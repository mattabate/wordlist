import sqlite3
import os
import yaml

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    DATABASE_FILE = config["db_file"]


def add_clues_last_updated_column(db_path: str):
    """
    Adds a 'clues_last_updated' column to the 'wordlist' table (if it doesn't already exist).
    Then sets all existing rows to the current timestamp (UTC).
    """

    if not os.path.exists(db_path):
        print(f"Database file '{db_path}' does not exist.")
        return

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # 1. Add the column (no default).
        cur.execute(
            """
            ALTER TABLE wordlist 
            ADD COLUMN clues_last_updated TEXT
            """
        )
        conn.commit()
        print("Successfully added 'clues_last_updated' column (no default).")
    except sqlite3.OperationalError as e:
        # If the column already exists, you'll get an error. You can ignore or handle it:
        if "duplicate column name" in str(e).lower():
            print("Column 'clues_last_updated' already exists. Skipping add.")
        else:
            raise

    try:
        # 2. Make sure any existing rows
        #    have 'clues_last_updated' set to the current timestamp.
        cur.execute(
            """
            UPDATE wordlist
            SET clues_last_updated = datetime('now')
            WHERE clues_last_updated IS NULL
            """
        )
        changed = cur.rowcount
        conn.commit()
        print(f"Updated {changed} rows to set 'clues_last_updated' to now.")
    except sqlite3.Error as e:
        print(f"SQLite error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    add_clues_last_updated_column(DATABASE_FILE)
