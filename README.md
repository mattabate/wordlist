# Wordlist for Puzzle Construction

**[► Download the Wordlist (JSON)](https://github.com/mattabate/wordlist/blob/main/data/matts_wordlist/scored_wordlist.json)**

**[► Download the Wordlist (TXT)](PLACEHOLDER_LINK_TXT)**

Welcome to my **Puzzle Constructor Wordlist** repository! This project provides a curated collection of words to help in creating crossword puzzles or other word-based puzzles. Additionally, it includes scripts and tools for scoring and filtering wordlists according to custom criteria.

## Whats in this Repo?

- A scored wordlist of 120,000 words.
- A pretrained AI/ML model that scores words (based on my preferences).  
- A script for for training your own AI/ML models based on your preferences (you'll need ex∂amples of words you do and don't like). 
- A tool for quickly labeling training data, that allows you to see real published clues for the words in your wordlist. 


## Table of Contents
1. [Project Description](#project-description)  
2. [Tools & Scripts](#tools--scripts)  
3. [Quickstart Setup](#quickstart-setup)  
4. [License & Credits](#license--credits)

## Project Description

### Initial Wordlist Candidate Set 

I formed an initial wordlist from various online wordlists, including but not limited to:
- [**Chris Jones Wordlist**](https://github.com/christophsjones/crossword-wordlist)
- [**Spread the Word(list)**](https://www.spreadthewordlist.com/)

A main problem was that these souces contained words and phrases that I would otherwise choose not to use. These bad-answers  were difficult to indentify efficiently and remove since the intial wordlist contained ~130K words.

### Labeling Words to Match my Preferences

I then built a tool for manually approving or rejecting words (from a final wordlist). The tool allows one to google the phrase and look at common clues from [**Crossword Tracker**](https://crosswordtracker.com/).

![Alt text](public/api_sort.png)

Using this tool, I sorted approximately ~35K words by hand:
- about ~24K were manually marked as approved words that I would be happy to put in a crossword puzzle, and
- about ~10K were removed from the wordlist entirely. These rejected words are now only stored in
**[this file](https://github.com/mattabate/wordlist/blob/main/data/raw/rejected.json)**.

_Note: This process took 10s of hours. While this effort greatly improved the list, unfamiliar or undesirable words still appear regularly._


### Training a Model on my Preferences 
After manual curation, an AI/ML model was trained to predict whether a new word would be acceptable. This is done in the following way:
- A training and test set were formed from the 35K labeled words, where every word (e.g., `"HOUSE"`) was put into a longer prompt (e.g., `"ANSWER: HOUSE"`).
- These prompts were then passed through an embedding model (transformer) to form a ≈1500 dimentional vector for each intial word. 
- Finally, a Support Vector Machine (SVM) was trained on the output of the embedding model. This SVM is stored as a pickle file in the repo and facilitates the on the fly scoring of new words. 

---

## Tools & Scripts

This section describes the scripts included in the `scripts/` directory and how to run them. You’ll find details such as:

- **Purpose** of each script  
- **Dependencies** you must install (or ensure are installed) before running  
- **Usage** instructions to run the script  
- **What to expect** (output, UI, etc.)  

Where relevant, placeholders for figures or screenshots are included to give an idea of what you’ll see when running the script.

---

### 1. `scripts/assess_svm.py`

**Purpose**  
This script evaluates the performance of a trained Support Vector Machine (SVM) model on two labeled sets of words:  
- A set of “approved” words  
- A set of “rejected” words  

It computes the accuracy of the model and prints the results to the terminal.

<details>
<summary>Key Steps</summary>

1. **Load configurations** from `scripts/config.yml`:  
   - Approved words file path (`WORDS_APPROVED`)  
   - Rejected words file path (`WORDS_REJECTED`)  
   - The pickle file with the trained SVM model (`MODEL_FILE_PATH`)  
   - Embedding model name from environment variable (with a default fallback)  

2. **Embed each word** in both the approved and rejected sets using the chosen OpenAI embedding model.

3. **Predict** whether each word is approved (1) or rejected (0).

4. **Compute accuracy** using `sklearn.metrics.accuracy_score`.

5. **Print** the accuracy to the terminal.
</details>

**Dependencies**
- `openai`  
- `dotenv`  
- `yaml`  
- `tqdm`  
- `sklearn`  
- Your custom `utils.json` module  
- `pickle` (standard library)  

**How to Run**
```bash
cd wordlist  # or the root directory of your project
python scripts/assess_svm.py
```

**Expected Output**  
A terminal printout displaying something like:

```
Embedding: 100%|█████████████████████████| 3500/3500 [00:12<00:00, 285.19it/s]
Model Accuracy on Provided Wordlists: 93.25%
```

---

### 2. `scripts/generate_scored_wordlist.py`

**Purpose**  
Generates a new JSON wordlist with scores assigned by the pretrained SVM model. Also outputs a sorted list of words from highest to lowest score.

<details>
<summary>Key Steps</summary>

1. **Load configurations** from `scripts/config.yml`:  
   - Paths for raw wordlist (`RAW_WORDLIST`), scored wordlist (`SCORED_WORDLIST`), and sorted wordlist (`SORTED_WORDLIST`).

2. **Load the raw wordlist** (`.json`), which typically includes ~120K words (or however large your file is).

3. **Call** `infer(data)` from `models/svm.py` to get `(word, score)` pairs.

4. **Normalize scores** into a 0–50 range.

5. **Save** two output files:  
   - `SCORED_WORDLIST` (JSON): keys are words, values are normalized scores  
   - `SORTED_WORDLIST` (JSON): a simple list of words sorted by descending score
</details>

**Dependencies**
- `json` (standard library)  
- `yaml`  
- Your custom `models.svm` module (requires a trained SVM)  

**How to Run**
```bash
cd wordlist
python scripts/generate_scored_wordlist.py
```

**Expected Output**  
- Two new files (JSON) created in the paths specified by your config:  
  - A scored wordlist (e.g., `scored_wordlist.json`).  
  - A sorted wordlist (e.g., `sorted_wordlist.json`).  

---

### 3. `scripts/manually_sort_words.py`

**Purpose**  
Launches a PyQt application that presents each word in a list, allowing you to quickly **approve** or **reject** the word. It also shows any published crossword puzzle clues (retrieved from [Crossword Tracker](https://crosswordtracker.com/)) for that word to help you decide.

<details>
<summary>Key Steps</summary>

1. **Load configurations** from `scripts/config.yml`, including:  
   - `RAW_WORDLIST` (or whichever wordlist you want to sort)  
   - `WORDS_APPROVED_JSON` and `WORDS_REJECTED`  
   - `WORDLIST_SOURCE` (the source file you’re actively processing)
   
2. **Display** each word in a GUI with relevant clues fetched from CrosswordTracker.  

3. **Allow** user actions:  
   - **Accept**: Moves word to the “approved” list  
   - **Reject**: Moves word to the “rejected” list  
   - **Pass**: Skips the current word (if you’re unsure)  
   - **Google**: Opens a browser tab searching for the word on Google (if you need more research)  
   - **Undo**: If you accidentally rejected a word, you can restore it  

4. **Save** your decisions to JSON files for future use.
</details>

**Dependencies**
- `requests` (for web calls)  
- `PyQt5` (for the GUI)  
- `beautifulsoup4` (for parsing crossword clue pages)  
- `yaml`  
- `webbrowser` (standard library)  
- `time`, `random` (standard library)  

**How to Run**
```bash
cd wordlist
python scripts/manually_sort_words.py
```

**What You’ll See**  
A PyQt window that displays:  
- The current word in large text  
- A list of up to ~6 crossword clues from [Crossword Tracker](https://crosswordtracker.com/)  
- Buttons for “Accept”, “Reject”, “Pass”, “Google”, and “Exit”  
- A text field for restoring (undoing) previously rejected words  

---

### 4. `scripts/train_svm.py`

**Purpose**  
Trains (or retrains) an SVM model using your manually labeled data of approved and rejected words.

<details>
<summary>Key Steps</summary>

1. **Load configurations** from `scripts/config.yml`:  
   - `WORDS_APPROVED` and `WORDS_REJECTED`  

2. **Load** the approved and rejected words from JSON.

3. **Call** `train_svm(approved, rejected)` from `models/svm.py`.

4. **Save** the trained SVM model (usually as a `.pkl` / pickle file) for later use in other scripts (like `assess_svm.py` or `generate_scored_wordlist.py`).
</details>

**Dependencies**
- `yaml`  
- `sklearn` (for SVM)  
- `openai` (if your training also uses embeddings during the process—depends on your `models.svm` implementation)  
- Your custom `utils.json` and `models.svm` modules  

**How to Run**
```bash
cd wordlist
python scripts/train_svm.py
```

**Expected Output**  
A trained SVM model is saved to the path specified in your code (often indicated in your `config.yml` or inside `train_svm.py`). The script may print logs to the terminal, e.g.:

```
Loading approved words: 24000
Loading rejected words: 10000
Embedding words... [ might take a while ]
Training SVM...
SVM trained and saved to data/svm_model.pkl
```

## Quickstart Setup

Get up and running quickly with these steps:

### Step 1: Clone the Repository

```bash
git clone https://github.com/mattabate/wordlist
cd wordlist
```

### Step 2: Set Up Package Management with Poetry

1. [Install Poetry](https://python-poetry.org/docs/#installation) if you haven't already.  
2. From the project root, install dependencies:

   ```bash
   poetry install
   ```

3. (Optional) Activate the virtual environment:

   ```bash
   poetry shell
   ```

> **Note**: Once installed, you can also run scripts via `poetry run python path/to/script.py` if you don’t want to activate the shell.

### Step 3: Configure Your Project

Create or edit your config file (for instance, `scripts/config.yml`) or environment variables to match your setup. Below is an example snippet of what you might add:

```yaml
search:
  max_walls: 42
  f_verbose: true
  f_save_words_used: false

wordlist:
  wordlist_json: "wordlist/word_list.json"
  disliked_json: "wordlist/disliked_words.json"
```

- Make sure you have a folder named `wordlist/`, along with:
  - `word_list.json` (your main wordlist).
  - `disliked_words.json` (if you have it).
- If you already have “approved” and “rejected” wordlists, place them in the appropriate JSON files under `data/raw/` or wherever your config expects them.  

### Step 4: (Optional) Train a Model

If you plan to use the AI/ML scoring, you may need a trained SVM model. Run:

```bash
poetry run python scripts/train_svm.py
```

- This trains a new model based on your approved/rejected word lists.  
- By default, it will save the trained model (as a `.pkl` file) to the location specified in `config.yml`.

### Step 5: Sort Your Words (If You Need to)

If you don’t have pre-sorted words, use the manual sorting tool:

```bash
poetry run python scripts/manually_sort_words.py
```

- This opens a GUI (PyQt) where you can **Accept**, **Reject**, or **Pass** on each word, helping you refine the list.  
- *Note*: This tool currently depends on having a working SVM model (so you might first need to run `train_svm.py` if the script references a model).

### Step 6: Generate a Scored Wordlist

Once you have a trained model (or if you’re using the provided pretrained model), you can score and sort your master wordlist:

```bash
poetry run python scripts/generate_scored_wordlist.py
```

- Produces a “scored” JSON file and a simple sorted list of words based on model predictions.

Below is a suggested **License & Credits** section that balances open collaboration with non-commercial usage. Feel free to adjust the wording to suit your preferences:

## License & Credits

### License
This project is distributed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/). In short, you are free to:

- **Share** — copy and redistribute the material in any medium or format  
- **Adapt** — remix, transform, and build upon the material  

…provided that:

1. **Attribution** – You give appropriate credit and indicate if changes were made.  
2. **NonCommercial** – You do not use the material for commercial purposes.  
3. **ShareAlike** – If you remix, transform, or build upon the material, you must distribute your contributions under the same license.

This license ensures that the wordlist remains open and community-driven while preventing others from using it in for-profit endeavors.

### Credits
- **Community Wordlists**  
  This project leverages many freely available and community-maintained wordlists, including (but not limited to) the [Chris Jones Wordlist](https://github.com/christophsjones/crossword-wordlist) and [Spread the Word(list)](https://www.spreadthewordlist.com/).  

- **Contributors**  
  Thanks to anyone who contributes suggestions, code, or other feedback. Your efforts help improve the quality of the puzzle wordlist.  
