"""score the words in the wordlist using a pretrained SVM model"""

import yaml

import utils.json
from models.svm import train_svm

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    WORDS_APPROVED = config["train_svm"]["WORDS_APPROVED"]
    WORDS_REJECTED = config["train_svm"]["WORDS_REJECTED"]

if __name__ == "__main__":

    approved = utils.json.load_json(WORDS_APPROVED)
    rejected = utils.json.load_json(WORDS_REJECTED)
    train_svm(approved, rejected)
