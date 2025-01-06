import sys
import random
import requests
import time
import webbrowser  # Added import for webbrowser
import yaml

from bs4 import BeautifulSoup
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
    QFrame,
    QMessageBox,
)

from models.svm import infer
from utils.json import append_json, remove_from_json, load_json

# manually_sort_words:
# - WORDS_APPROVED: "data/raw/approved.json"
# - WORDS_OMITTED: "data/raw/rejected.json"

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    RAW_WORDLIST = config["manually_sort_words"]["RAW_WORDLIST"]
    WORDS_APPROVED_JSON = config["manually_sort_words"]["WORDS_APPROVED"]
    WORDS_REJECTED = config["manually_sort_words"]["WORDS_REJECTED"]
    WORDLIST_SOURCE = config["manually_sort_words"]["WORDLIST_SOURCE"]
    # RAW_WORDLIST = config["generate_scored_wordlist"]["RAW_WORDLIST"]
    # SCORED_WORDLIST = config["generate_scored_wordlist"]["SCORED_WORDLIST"]
    # SORTED_WORDLIST = config["generate_scored_wordlist"]["SORTED_WORDLIST"]


_max_words_considered = 2000


class WordSortingApp(QWidget):
    def __init__(self):
        super().__init__()

        self.source = WORDLIST_SOURCE

        words_condiered = load_json(WORDLIST_SOURCE)
        if len(words_condiered) > _max_words_considered:
            words_condiered = words_condiered[:_max_words_considered]
        scored_words = infer(words_condiered)

        self.words_considered = [word for word, _ in scored_words[::-1]]

        self.words_omitted = load_json(WORDS_REJECTED)
        self.words_approved = load_json(WORDS_APPROVED_JSON)
        self.words_seen = set(self.words_omitted + self.words_approved)

        self.total_words = len(self.words_considered)  # Total number of words
        self.num_printed = 6
        self.params = {"search_redirect": "True"}
        self.headers = {"User-Agent": "Mozilla/5.0"}

        self.word_index = 0
        self.initUI()
        self.process_next_word()

    def initUI(self):
        self.setWindowTitle("Word Sorting Application")

        # Set window size and background color
        self.resize(700, 500)
        self.setStyleSheet("background-color: #f0f0f0;")

        # Progress label
        self.progress_label = QLabel("", self)
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setFont(QFont("Arial", 12))
        self.progress_label.setStyleSheet("color: #666666;")

        # Word label (now selectable)
        self.word_label = QLabel("", self)
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.word_label.setStyleSheet("color: #333333;")
        self.word_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.word_label.setToolTip("Select and copy this word")
        self.word_label.setCursor(Qt.IBeamCursor)

        # Divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        # Clues text box
        self.clues_text = QTextEdit(self)
        self.clues_text.setReadOnly(True)
        self.clues_text.setFont(QFont("Arial", 12))
        self.clues_text.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cccccc; padding: 5px;"
        )

        # Buttons
        self.accept_button = QPushButton("Accept ✅", self)
        self.reject_button = QPushButton("Reject ❌", self)
        self.pass_button = QPushButton("Pass ⏭️", self)
        self.google_button = QPushButton("Google 🔍", self)  # Added Google button
        self.exit_button = QPushButton("Exit 🚪", self)

        self.accept_button.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 10px; font-size: 14px;"
        )
        self.reject_button.setStyleSheet(
            "background-color: #f44336; color: white; padding: 10px; font-size: 14px;"
        )
        self.pass_button.setStyleSheet(
            "background-color: #2196F3; color: white; padding: 10px; font-size: 14px;"
        )
        self.google_button.setStyleSheet(  # Style for Google button
            "background-color: #FFA500; color: white; padding: 10px; font-size: 14px;"
        )
        self.exit_button.setStyleSheet(
            "background-color: #757575; color: white; padding: 10px; font-size: 14px;"
        )

        self.accept_button.clicked.connect(self.accept_word)
        self.reject_button.clicked.connect(self.reject_word)
        self.pass_button.clicked.connect(self.pass_word)
        self.google_button.clicked.connect(self.google_word)  # Connected Google button
        self.exit_button.clicked.connect(self.exit_app)

        # Undo input field and button
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

        # Layouts
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.accept_button)
        button_layout.addWidget(self.reject_button)
        button_layout.addWidget(self.pass_button)
        button_layout.addWidget(self.google_button)  # Added Google button to layout
        button_layout.addWidget(self.exit_button)

        undo_layout = QHBoxLayout()
        undo_layout.addWidget(self.undo_input)
        undo_layout.addWidget(self.undo_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.progress_label)
        main_layout.addWidget(self.word_label)
        main_layout.addWidget(line)
        main_layout.addWidget(self.clues_text)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(undo_layout)

        self.setLayout(main_layout)
        self.show()

    def process_next_word(self):
        if self.word_index >= self.total_words:
            QMessageBox.information(self, "Completed", "All words have been processed.")
            self.close()
            return

        # Update progress label
        current_word_number = self.word_index + 1  # Since index starts at 0
        self.progress_label.setText(f"Word {current_word_number} of {self.total_words}")

        word = self.words_considered[self.word_index]
        self.current_word = word

        if word in self.words_seen:
            self.word_index += 1
            self.process_next_word()
            return

        self.word_label.setText(f"{word.upper()}")

        url = f"https://crosswordtracker.com/answer/{word.lower()}/"

        try:
            response = requests.get(url, headers=self.headers, params=self.params)
            code = response.status_code
        except:
            code = 1

        clues_text = ""
        if code != 200:
            # No clues found, make the clues text box pink
            self.clues_text.setStyleSheet(
                "background-color: #ffe6f2; border: 1px solid #ff80bf; padding: 5px;"
            )
            clues_text = f"No clues found for '{word}'."
        else:
            time.sleep(random.uniform(0.5, 1.25))
            soup = BeautifulSoup(response.text, "html.parser")
            clue_container = soup.find("h3", string="Referring crossword puzzle clues")
            clues = []
            if clue_container:
                clue_container = clue_container.find_next_sibling("div")
                clues = clue_container.find_all("li")
                clues_text = "\n".join(
                    [f"- {clue.get_text()}" for clue in clues[: self.num_printed]]
                )
                # Reset clues text box style
                self.clues_text.setStyleSheet(
                    "background-color: #ffffff; border: 1px solid #cccccc; padding: 5px;"
                )
            else:
                # No clues found, make the clues text box pink
                self.clues_text.setStyleSheet(
                    "background-color: #ffe6f2; border: 1px solid #ff80bf; padding: 5px;"
                )
                clues_text = f"No clues found for '{word}'."

        self.clues_text.setPlainText(clues_text)

    def accept_word(self):
        word = self.current_word
        append_json(WORDS_APPROVED_JSON, word)
        remove_from_json(WORDLIST_SOURCE, word)
        self.word_index += 1
        self.process_next_word()

    def reject_word(self):
        word = self.current_word
        append_json(WORDS_REJECTED, word)
        remove_from_json(RAW_WORDLIST, word)
        remove_from_json(WORDLIST_SOURCE, word)
        self.word_index += 1
        self.process_next_word()

    def pass_word(self):
        self.word_index += 1
        self.process_next_word()

    def google_word(self):  # Added function to handle Google search
        word = self.current_word
        query = word
        url = f"https://www.google.com/search?q={query}"
        webbrowser.open_new_tab(url)

    def undo_rejection(self):
        entered_word = self.undo_input.toPlainText().strip().upper()
        print("word to undo:", entered_word)
        if remove_from_json(WORDS_REJECTED, entered_word):
            append_json(RAW_WORDLIST, entered_word)
            append_json(WORDS_APPROVED_JSON, entered_word)
            QMessageBox.information(
                self, "Undo Successful", f"'{entered_word}' has been restored."
            )
        else:
            QMessageBox.warning(
                self, "Undo Failed", f"'{entered_word}' was not found in omitted words."
            )

    def exit_app(self):
        self.close()


if __name__ == "__main__":

    if not load_json(WORDLIST_SOURCE):
        print("No words to process.")
        exit()

    app = QApplication(sys.argv)
    ex = WordSortingApp()
    sys.exit(app.exec_())
