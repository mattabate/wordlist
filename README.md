
# Wordlist for Puzzle Construction

**[► Download Wordlist (TXT)](https://github.com/mattabate/wordlist/blob/main/matts_wordlist/scored_wordlist.txt)**

**[► Download Wordlist (JSON)](https://github.com/mattabate/wordlist/blob/main/matts_wordlist/scored_wordlist.json)**  

Welcome to my **Puzzle Constructor Wordlist** repository! This project provides a curated collection of words to aid you in creating crossword puzzles and other word-based games. Here you'll find: 

- A free-to-use scored wordlist of ~260,000 words.
- A pretrained AI/ML model that scores words (based on my preferences).  
- A set of scrpts for training your own AI/ML model to score words (using examples of words you like and dislike).

A technical description and quickstart guide is provided below.  Email me with questions: mabate13@gmail.com.

## Table of Contents

1. [AI/ML Scoring Algorithm]()
2. [Quickstart](#quickstart)
3. [License & Credits](#license--credits)

## 1. AI/ML Scoring Algorithm

![Training Diagram](wordlist/public/training_diagram.svg)
*Figure 1: Scoring Approach — Words and clues are vectorized using an embedding model, and an SVM is trained on labeled vectors to score new words in the future.*

Given a new wordlist, the scoring method of this repo uses an embedding model to provide a 1536-dimensional vector for every word. A Support Vector Machine (SVM) is trained on labeled words, and this SVM then allows for scoring new words.


### Training a Model on my Preferences 
After manual curation, an AI/ML model was trained to predict whether a new word would be acceptable. This is done in the following way:
- A training and test set were formed from the 35K labeled words, where every word (e.g., `"HOUSE"`) was put into a longer prompt (e.g., `"ANSWER: HOUSE"`).
- These prompts were then passed through an embedding model (transformer) to form a ≈1500 dimentional vector for each intial word. 
- Finally, a Support Vector Machine (SVM) was trained on the output of the embedding model (`text-embedding-3-small`). This SVM is stored as a pickle file in the repo and facilitates the on the fly scoring of new words. 



## 2. Quickstart

In this quickstart guide, you'll train your own scoring model and create a scored wordlist.

![Project Overview](wordlist/public/project_overview.svg)
*Figure 1: Project Overview*

### 2.1 Clone and Install Dependencies


Clone the repo and change into the project directory:

```bash
git clone git@github.com:mattabate/wordlist.git
cd wordlist
```

Initialize and install all dependencies with:

```bash
poetry init
poetry install
```

### 2.2 Create the Wordlist Database

Set up the SQLite database by running:

```bash
poetry run python3 scripts/create_db.py
```

This creates a `wordlist.db` file with key tables such as:

- **words** – stores each word, its clues, and status (`approved`, `rejected`, or `unchecked`).
- **sources** – records details about each word source.
- **word_model_score** – logs scores from various models.

### 2.3 Add a New Wordlist Source

To import words from a new wordlist (in Crossword Constructor TXT format) to your database, follow these steps:

1. **Create a Folder**: In the `sources/` directory, create a folder for the wordlist you'd like to incorperate (e.g., `sources/matts_wordlist/`).
2. **Add Files**:  
   - Place your scored wordlist TXT file into this folder.
   - Create a `config.yaml` with:
     ```yaml
     name: "matts_wordlist"
     url: "https://github.com/mattswordlist/wordlist"
     file_path: "sources/matts_wordlist/matts_wordlist.txt"
     ```
3. **Import to Database**:  
   Run the following command to add the words (and their scores) to the database:
   ```bash
   poetry run python3 scripts/add_wordlist --input matts_wordlist
   ```

*Repeat these steps for each additional wordlist source you want to add.*

> **Note:** As a starting example, I've provided my personal wordlist in the `quickstart/matts_wordlist.txt`. This can be used as a first example. For additional resources and wordlists, consider the following:
> - [Chris's Jones Wordlist](https://github.com/christophsjones/crossword-wordlist)
> - [Spread the Word(list)](https://www.spreadthewordlist.com/)
> - [Peter Broda's Wordlist](https://peterbroda.me/crosswords/wordlist/)




To import a scored wordlist (in Crossword Constructor TXT format), follow these steps:

1. **Create a Folder**: In the `sources/` directory, create a folder for your wordlist (e.g., `sources/matts_wordlist/`).
2. **Add Files**:  
   - Place your scored wordlist TXT file into this folder.
   - Create a `config.yaml` with content like:
     ```yaml
     name: "matts_wordlist"
     url: "https://github.com/mattswordlist/wordlist"
     file_path: "sources/matts_wordlist/matts_wordlist.txt"
     ```
3. **Import to Database**:  
   Run the following command to add the words (and their scores) to the database:
   ```bash
   poetry run python3 scripts/add_wordlist --input matts_wordlist
   ```

*Repeat these steps for each additional wordlist source you want to add. (See the Community Wordlists section for recommendations.)*

### 2.5 Manually Sort Words

Refine your wordlist by manually approving or rejecting words. This curated data is essential for training your model.

![Sorting Tool](wordlist/public/api_sort.png)

- **Input File**:  
  The tool uses `inputs/manually_sort_words.json` for its word queue. If the file or `inputs/` directory doesn’t exist, it will be created automatically on the first run.
  
- **Run the Tool**:  
  Launch the sorting interface with:
  ```bash
  poetry run python3 scripts/manually_sort_words.py
  ```
  
- **Interface Features**:  
  The application displays one word (with clues) at a time. You can:
  - **Accept** a word.
  - **Reject** a word.
  - **Pass** if unsure.
  - **Google** the word for more context.
  - **Undo** a rejection if needed.

### 2.6 Train the SVM Model

Once you've sorted your words, train an SVM model using your approved and rejected words. This model will help score the words based on your preferences.

Run the training script with:

```bash
poetry run python3 scripts/train_svm.py
```

The script will:
- Load approved and rejected words from the database.
- Train an SVM model and display its score and training duration.
- Prompt you to save the model as a pickle file in the `models/` directory (with metadata recorded in the database).

### 2.7 Generate Scored Wordlist

After training your model, score the words in your database using:

```bash
poetry run python3 scripts/score_words.py --model <model_id>
```

This command computes scores for your words based on the trained model and saves them to the database. Run this step once per model to generate the final wordlist (in Crossword Constructor format).

## 2. License & Credits

### License

This project is distributed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/). In short, you are free to:

- **Share** — copy and redistribute the material.
- **Adapt** — remix, transform, and build upon the material.

*Under the conditions that you:*

1. **Give Attribution** – Credit the original source.
2. **Use Non-Commercially** – No commercial use allowed.
3. **ShareAlike** – Distribute modifications under the same license.

### Credits

- **Community Wordlists**:  
  This project builds upon numerous community wordlists, including:
  - [Chris's Jones Wordlist](https://github.com/christophsjones/crossword-wordlist)
  - [Spread the Word(list)](https://www.spreadthewordlist.com/)
  - [Peter Broda's Wordlist](https://peterbroda.me/crosswords/wordlist/)

- **Contributors**:  
  Thank you to everyone who has contributed suggestions, code, and feedback—your efforts help make this project even better!
