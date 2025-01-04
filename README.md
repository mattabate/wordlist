# Wordlist for Puzzle Construction

**[► Download the Wordlist (JSON)](https://github.com/mattabate/wordlist/blob/init/data/matts_wordlist/scored_wordlist.json)**

**[► Download the Wordlist (TXT)](PLACEHOLDER_LINK_TXT)**

Welcome to the **Puzzle Constructor Wordlist** repository! This project provides a curated collection of words (originally ~130K, manually reduced and refined to ~24K) to help in creating crossword puzzles or other word-based puzzles. Additionally, it includes scripts and tools for scoring and filtering these words according to custom criteria.

## Table of Contents
1. [Project Description](#project-description)  
2. [Tools & Scripts](#tools--scripts)  
3. [Usage Instructions](#usage-instructions)  
4. [Required Packages](#required-packages)  
5. [License & Credits](#license--credits)

---

## Project Description

This collection of words was assembled by gathering various online wordlists, including but not limited to:
- **Source 1**  
- **Source 2**  
- _Other sources whose names I forgot_

### Manual Sorting
- Initially started with ~130K words.
- Manually approved ~24K words and removed ~10K words over the course of tens of hours.
- A custom tool (not included in this repo) allowed for rapid manual sorting:
  - Presented ~5 possible clues for each candidate word.
  - Gave the option to **accept**, **reject**, or **abstain**.
  - Integrated a quick search (e.g., Google) to research unknown words.
- While this effort greatly improved the list, unfamiliar or undesirable words still appear from time to time.

### Model-Based Scoring
- After manual curation, an SVM model was trained to predict whether a new word would be acceptable.
- The process involves creating embeddings for each word using an OpenAI embedding model:
  1. Convert a word (e.g., `"HOUSE"`) into a longer prompt (e.g., `"ANSWER: HOUSE"`).
  2. Generate an embedding vector (≈1500 dimensions).
  3. Pass this vector into a **pretrained SVM** (saved as a pickle file).
- **Note:** The script for training the SVM itself and the manual sorting tool are not yet included in this repository.

---

## Tools & Scripts

Currently, the main script included is for **scoring** words via the pretrained SVM:

- **`scripts/generate_scored_wordlist.py`**  
  Generates a scored wordlist in the `/wordlist` directory based on the SVM predictions.

Future plans (not yet included in this repo) involve:
- The **manual sorting tool** with integrated clue display and online search.
- The **SVM training script** to retrain or update the model with additional data.

For reference, see [the script on GitHub (placeholder)](PLACEHOLDER_LINK_SCRIPT) if you’d like to track its development progress.

---

## Usage Instructions

To score words using the existing model:

1. **Obtain an OpenAI API key**:  
   - Copy `.env.template` to a new file called `.env`.
   - Insert your OpenAI API key in the `OPENAI_API_KEY` field.
2. **Install required dependencies** (see [Required Packages](#required-packages)).
3. **Run the script** to generate a new scored wordlist:
   ```bash
   cd wordlist
   python3 scripts/generate_scored_wordlist.py
