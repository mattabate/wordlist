#!/usr/bin/env python3
"""
Grid-based Word Sorting Application using PyQt5 and SQLite.

This version shows four words at a time in a grid. Each word card contains
its own buttons for Accept, Reject, Pass, and Google. A global progress label,
undo rejection input, and Exit button are provided below the grid.
"""

import sys
import webbrowser
import yaml
import sqlite3

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QMessageBox,
)

from models.database import get_clues_for_word, update_word_status, get_words
from models.svm import infer
from utils.json import remove_from_json, load_json

# Load configuration
with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    WORDLIST_SOURCE = config["intake_manually_sort_words"]
    DB_PATH = config["db_file"]

_max_words_considered = 2000


class WordCard(QWidget):
    """
    A widget representing a single word with its clues and control buttons.
    """

    def __init__(self, parent, process_callbacks):
        super().__init__(parent)
        self.parent_app = parent  # Reference to the main app (for callbacks)
        self.current_word = None  # The word currently loaded on this card
        self.process_callbacks = (
            process_callbacks  # Dictionary mapping action names to callbacks
        )
        self.initUI()

    def initUI(self):
        self.word_label = QLabel("", self)
        self.word_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.clues_text = QTextEdit(self)
        self.clues_text.setReadOnly(True)
        self.clues_text.setFont(QFont("Arial", 12))
        self.clues_text.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cccccc; padding: 5px;"
        )

        # Create the buttons for this card
        self.accept_button = QPushButton("Accept ✅", self)
        self.reject_button = QPushButton("Reject ❌", self)
        self.pass_button = QPushButton("Pass ⏭️", self)
        self.google_button = QPushButton("Google 🔍", self)

        # Connect each button to its action via a lambda that passes self and the current word
        self.accept_button.clicked.connect(lambda: self.process("accept"))
        self.reject_button.clicked.connect(lambda: self.process("reject"))
        self.pass_button.clicked.connect(lambda: self.process("pass"))
        self.google_button.clicked.connect(lambda: self.process("google"))

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.reject_button)
        button_layout.addWidget(self.pass_button)
        button_layout.addWidget(self.google_button)

        layout = QVBoxLayout()
        layout.addWidget(self.word_label)
        layout.addWidget(self.clues_text)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def load_word(self, word):
        """
        Loads a new word into this card. If no word is provided, disable the controls.
        """
        self.current_word = word
        if word is None:
            self.word_label.setText("No more words")
            self.clues_text.clear()
            self.accept_button.setEnabled(False)
            self.reject_button.setEnabled(False)
            self.pass_button.setEnabled(False)
            self.google_button.setEnabled(False)
        else:
            self.word_label.setText(word.upper())
            clues = get_clues_for_word(word, DB_PATH)
            if not clues:
                # If no clues are found, display a notice with a pink background
                self.clues_text.setStyleSheet(
                    "background-color: #ffe6f2; border: 1px solid #ff80bf; padding: 5px;"
                )
                self.clues_text.setPlainText(f"No clues found for '{word}'.")
            else:
                self.clues_text.setStyleSheet(
                    "background-color: #ffffff; border: 1px solid #cccccc; padding: 5px;"
                )
                self.clues_text.setPlainText(clues)

    def process(self, action):
        """
        Called when one of the action buttons is clicked.
        Delegates processing to the provided callback.
        """
        if self.current_word is None:
            return
        callback = self.process_callbacks.get(action)
        if callback:
            callback(self, self.current_word)


class WordSortingApp(QWidget):
    def __init__(self):
        super().__init__()
        # Initialize database connection
        self.conn = sqlite3.connect(DB_PATH)

        self.source = WORDLIST_SOURCE
        self.words_omitted = get_words(conn=self.conn, status="rejected")
        self.words_approved = get_words(conn=self.conn, status="approved")
        self.words_seen = set(self.words_omitted + self.words_approved)

        words_considered = load_json(WORDLIST_SOURCE)
        words_considered = [
            word for word in words_considered if word not in self.words_seen
        ]
        if len(words_considered) > _max_words_considered:
            words_considered = words_considered[:_max_words_considered]
        scored_words = infer("scripts/models/saved_preferences.pkl", words_considered)
        self.words_considered = [word for word, _ in scored_words[::-1]]

        # Retrieve words already processed (approved or rejected)
        self.total_words = len(self.words_considered)
        self.word_index = 0  # Global pointer into the list of words

        self.initUI()
        self.load_next_words()

    def initUI(self):
        self.setWindowTitle("Word Sorting Application - Grid View")
        self.resize(900, 700)
        self.setStyleSheet("background-color: #f0f0f0;")

        self.progress_label = QLabel("", self)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setFont(QFont("Arial", 14))

        # Create a grid layout for 4 word cards (2 rows x 2 columns)
        self.grid_layout = QGridLayout()
        self.cards = []
        process_callbacks = {
            "accept": self.accept_word,
            "reject": self.reject_word,
            "pass": self.pass_word,
            "google": self.google_word,
        }
        for i in range(4):
            card = WordCard(self, process_callbacks)
            self.cards.append(card)
            self.grid_layout.addWidget(card, i // 2, i % 2)

        # Global undo rejection controls
        self.undo_input = QTextEdit(self)
        self.undo_input.setFont(QFont("Arial", 12))
        self.undo_input.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cccccc; padding: 5px;"
        )
        self.undo_input.setPlaceholderText("Enter word to undo rejection...")
        self.undo_input.setFixedHeight(40)

        self.undo_button = QPushButton("Undo Rejection", self)
        self.undo_button.setStyleSheet(
            "background-color: #FFD700; color: black; padding: 10px; font-size: 14px;"
        )
        self.undo_button.clicked.connect(self.undo_rejection)

        # Global exit button
        self.exit_button = QPushButton("Exit 🚪", self)
        self.exit_button.setStyleSheet(
            "background-color: #757575; color: white; padding: 10px; font-size: 14px;"
        )
        self.exit_button.clicked.connect(self.exit_app)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.undo_input)
        bottom_layout.addWidget(self.undo_button)
        bottom_layout.addWidget(self.exit_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.progress_label)
        main_layout.addLayout(self.grid_layout)
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)
        self.show()

    def update_progress(self):
        processed = min(self.word_index, self.total_words)
        self.progress_label.setText(
            f"Processed {processed} of {self.total_words} words."
        )

    def get_next_word(self):
        """
        Returns the next available word from the list, skipping words already seen.
        """
        while self.word_index < self.total_words:
            word = self.words_considered[self.word_index]
            self.word_index += 1
            if word in self.words_seen:
                remove_from_json(WORDLIST_SOURCE, word)
                continue
            return word
        return None

    def load_next_words(self):
        """
        Loads the next available word into each card.
        """
        for card in self.cards:
            next_word = self.get_next_word()
            card.load_word(next_word)
        self.update_progress()

    def process_card_action(self, card, word, new_status=None):
        """
        Generalized processing for a card’s action. If a new_status is provided (e.g., "approved"
        or "rejected"), update the database and remove the word from the source JSON.
        Then load the next word into that card.
        """
        if new_status in ["approved", "rejected"]:
            try:
                update_word_status(self.conn, word, new_status)
                remove_from_json(WORDLIST_SOURCE, word)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error processing '{word}': {e}")
        next_word = self.get_next_word()
        card.load_word(next_word)
        self.update_progress()

    def accept_word(self, card, word):
        self.process_card_action(card, word, new_status="approved")

    def reject_word(self, card, word):
        self.process_card_action(card, word, new_status="rejected")

    def pass_word(self, card, word):
        self.process_card_action(card, word, new_status=None)

    def google_word(self, card, word):
        url = f"https://www.google.com/search?q={word}"
        webbrowser.open_new_tab(url)

    def undo_rejection(self):
        entered_word = self.undo_input.toPlainText().strip().upper()
        try:
            if update_word_status(self.conn, entered_word, "approved"):
                QMessageBox.information(
                    self, "Undo Successful", f"'{entered_word}' has been restored."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Undo Failed",
                    f"'{entered_word}' was not found in omitted words.",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to undo rejection for '{entered_word}': {e}"
            )

    def exit_app(self):
        self.close()

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
        event.accept()


if __name__ == "__main__":
    if not load_json(WORDLIST_SOURCE):
        print("No words to process.")
        exit()
    app = QApplication(sys.argv)
    ex = WordSortingApp()
    sys.exit(app.exec_())
