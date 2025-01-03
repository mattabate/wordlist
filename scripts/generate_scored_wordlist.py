import json
from models.svm import infer
import yaml

with open("scripts/config.yml") as file:
    config = yaml.safe_load(file)
    RAW_WORDLIST = config["RAW_WORDLIST"]
    SCORED_WORDLIST = config["SCORED_WORDLIST"]
    SORTED_WORDLIST = config["SORTED_WORDLIST"]

if __name__ == "__main__":
    with open(RAW_WORDLIST) as file:
        data = json.load(file)

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
