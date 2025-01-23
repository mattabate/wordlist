"""score the words in the wordlist using a pretrained SVM model"""

import json
import yaml

from models.svm import infer
import utils.printing

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    RAW_WORDLIST = config["generate_scored_wordlist"]["RAW_WORDLIST"]
    SCORED_WORDLIST = config["generate_scored_wordlist"]["SCORED_WORDLIST"]
    SORTED_WORDLIST = config["generate_scored_wordlist"]["SORTED_WORDLIST"]

if __name__ == "__main__":
    with open(RAW_WORDLIST) as file:
        data = json.load(file)

    print(
        f"{utils.printing.c_yellow}Number of words:{utils.printing.c_end} {len(data)}"
    )

    model_output = infer(data)

    # get max and min scores
    max_score = max(model_output, key=lambda x: x[1])
    min_score = min(model_output, key=lambda x: x[1])

    # normalize so they are 0 - 50
    matt_scores = {
        w: int((s - min_score[1]) / (max_score[1] - min_score[1]) * 50)
        for w, s in model_output
    }

    with open(SCORED_WORDLIST, "w") as file:
        json.dump(matt_scores, file, indent=4)

    with open(SORTED_WORDLIST, "w") as file:
        json.dump([w for w, _ in model_output], file, indent=4)
