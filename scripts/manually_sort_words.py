#!/usr/bin/env python3
"""
Single-Panel Word Sorting Application with Enhanced UI/UX.
Displays one word at a time with its clues and action buttons.
"""
import os
import sqlite3
import sys
import webbrowser

from dotenv import load_dotenv
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
    QMessageBox,
    QSizePolicy,
)

from wordlist.lib.database import (
    get_clues_for_word,
    update_word_status,
    get_words,
    sort_words_by_score,
)

from wordlist.utils.json import remove_from_json, load_json, write_json
from wordlist.utils.printing import c_blue, c_end

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
DB_PATH = os.getenv("SQLITE_DB_FILE")
WORDLIST_SOURCE = "manually_sort_words.json"
inputs_dir = "inputs"
WORDLIST_SOURCE = os.path.join(inputs_dir, WORDLIST_SOURCE)

if not os.path.exists(WORDLIST_SOURCE):
    print(
        f"""{c_blue}HALT{c_end}: Is this your first time running this script?
I created a new directory and file called 'inputs'.
Add the strings you are interested in sorting and try again.
"""
    )
    write_json(WORDLIST_SOURCE, [])
    exit()

_max_words_considered = 2000


class WordCard(QWidget):
    """
    A widget representing a single word with its clues and control buttons.
    """

    def __init__(self, parent, process_callbacks):
        super().__init__(parent)
        self.parent_app = parent
        self.current_word = None
        self.process_callbacks = process_callbacks
        self.initUI()

    def initUI(self):
        # Word label in bold, clear and large
        self.word_label = QLabel("", self)
        self.word_label.setFont(QFont("Arial", 26, QFont.Bold))
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # Clues text area with extra padding and light background (no heavy border)
        self.clues_text = QTextEdit(self)
        self.clues_text.setReadOnly(True)
        self.clues_text.setFont(QFont("Arial", 14))
        self.clues_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #F9F9F9;
                border: none;
                padding: 10px;
            }
            """
        )

        # Create action buttons with uniform styling and size
        button_style = (
            "QPushButton { background-color: #007ACC; color: white; border: none; "
            "padding: 10px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #005999; }"
            "QPushButton:disabled { background-color: #cccccc; }"
        )

        self.accept_button = QPushButton("Accept ✅", self)
        self.reject_button = QPushButton("Reject ❌", self)
        self.pass_button = QPushButton("Pass ⏭️", self)
        self.google_button = QPushButton("Google 🔍", self)
        for btn in [
            self.accept_button,
            self.reject_button,
            self.pass_button,
            self.google_button,
        ]:
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Connect buttons to their respective actions
        self.accept_button.clicked.connect(lambda: self.process("accept"))
        self.reject_button.clicked.connect(lambda: self.process("reject"))
        self.pass_button.clicked.connect(lambda: self.process("pass"))
        self.google_button.clicked.connect(lambda: self.process("google"))

        # Layout for buttons - equal spacing
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.reject_button)
        button_layout.addWidget(self.pass_button)
        button_layout.addWidget(self.google_button)

        # Overall layout for the word card
        layout = QVBoxLayout()
        layout.addWidget(self.word_label)
        layout.addWidget(self.clues_text)
        layout.addLayout(button_layout)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)

    def load_word(self, word, score):
        """
        Loads a new word into the card. If no word is provided, disable controls.
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
            self.word_label.setText("    " + word.upper() + f"  ({round(score, 3)})")
            clues = get_clues_for_word(word, DB_PATH)
            if not clues:
                self.clues_text.setStyleSheet(
                    """
                    QTextEdit {
                        background-color: #FFF2F2;
                        border: none;
                        padding: 10px;
                        color: #AA0000;
                    }
                    """
                )
                self.clues_text.setPlainText(f"No clues found for '{word}'.")
            else:
                self.clues_text.setStyleSheet(
                    """
                    QTextEdit {
                        background-color: #F9F9F9;
                        border: none;
                        padding: 10px;
                        color: black;
                    }
                    """
                )
                self.clues_text.setPlainText(clues)

    def process(self, action):
        """
        Invokes the callback for the given action with this card and its word.
        """
        if self.current_word is None:
            return
        callback = self.process_callbacks.get(action)
        if callback:
            callback(self, self.current_word)


class WordSortingApp(QWidget):
    def __init__(self):
        super().__init__()
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


        word_scores_dict =  sort_words_by_score(
            self.conn, words_considered, 4
        )

        self.scores_dict = word_scores_dict
        order = "asc"
        self.words_considered = sorted([w for w in word_scores_dict.keys()], key=lambda w: word_scores_dict.get(w, 0), reverse=order == "desc")

        self.total_words = len(self.words_considered)
        self.word_index = 0  # Pointer into words_considered

        self.initUI()
        self.load_next_word()

    def initUI(self):
        self.setWindowTitle("Word Sorting Application")
        self.resize(700, 600)
        self.setStyleSheet("background-color: #FFFFFF;")

        # Progress label for tracking processing status
        self.progress_label = QLabel("", self)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setFont(QFont("Arial", 16))
        self.progress_label.setStyleSheet("color: #333333;")

        # Single word card
        process_callbacks = {
            "accept": self.accept_word,
            "reject": self.reject_word,
            "pass": self.pass_word,
            "google": self.google_word,
        }
        self.card = WordCard(self, process_callbacks)

        # Undo rejection text input and button with friendly styling
        self.undo_input = QTextEdit(self)
        self.undo_input.setFont(QFont("Arial", 14))
        self.undo_input.setStyleSheet(
            """
            QTextEdit {
                background-color: #F9F9F9;
                border: 1px solid #DDDDDD;
                padding: 8px;
            }
            """
        )
        self.undo_input.setPlaceholderText("Enter word to undo rejection...")
        self.undo_input.setFixedHeight(40)

        undo_button_style = (
            "QPushButton { background-color: #FF9800; color: white; border: none; "
            "padding: 10px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #E68900; }"
        )
        self.undo_button = QPushButton("Undo Rejection", self)
        self.undo_button.setStyleSheet(undo_button_style)
        self.undo_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.undo_button.clicked.connect(self.undo_rejection)

        # Exit button with matching style
        exit_button_style = (
            "QPushButton { background-color: #9E9E9E; color: white; border: none; "
            "padding: 10px; font-size: 14px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #7E7E7E; }"
        )
        self.exit_button = QPushButton("Exit 🚪", self)
        self.exit_button.setStyleSheet(exit_button_style)
        self.exit_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.exit_button.clicked.connect(self.exit_app)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)
        bottom_layout.addWidget(self.undo_input)
        bottom_layout.addWidget(self.undo_button)
        bottom_layout.addWidget(self.exit_button)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.progress_label)
        main_layout.addWidget(self.card)
        main_layout.addLayout(bottom_layout)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(30, 30, 30, 30)

        self.setLayout(main_layout)
        self.show()

    def update_progress(self):
        processed = min(self.word_index, self.total_words)
        self.progress_label.setText(
            f"Processed {processed} of {self.total_words} words."
        )

    def get_next_word(self):
        """
        Returns the next available word, skipping those already seen.
        """
        while self.word_index < self.total_words:
            word = self.words_considered[self.word_index]
            self.word_index += 1
            if word in self.words_seen:
                remove_from_json(WORDLIST_SOURCE, word)
                continue
            return word
        return None

    def load_next_word(self):
        """
        Loads the next word into the single card.
        """
        next_word = self.get_next_word()
        self.card.load_word(next_word, self.scores_dict.get(next_word, 0))
        self.update_progress()

    def process_card_action(self, card, word, new_status=None):
        """
        Process an action on the word. Updates the database if a new_status is provided,
        removes the word from the JSON file, and loads the next word.
        """
        if new_status in ["approved", "rejected"]:
            try:
                update_word_status(self.conn, word, new_status)
                remove_from_json(WORDLIST_SOURCE, word)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error processing '{word}': {e}")
        self.load_next_word()

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
                    f"'{entered_word}' was not found among rejected words.",
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
