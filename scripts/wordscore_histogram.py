#!/usr/bin/env python3
"""
Generate a histogram of word scores from a JSON file.

Usage:
    python3 wordscore_histogram.py --input scores.json

The histogram will have buckets of 2 units, ranging from 0 to 50 on the x-axis.
"""

import argparse
import json
import sys

import matplotlib.pyplot as plt


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing the input file path.
    """
    parser = argparse.ArgumentParser(
        description="Generate a histogram of word scores from a JSON file."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the input JSON file containing word-score pairs.",
    )
    return parser.parse_args()


def load_scores(json_file):
    """
    Load word scores from a JSON file.

    Args:
        json_file (str): Path to the JSON file.

    Returns:
        list of int: List of scores.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: If the JSON file is not properly formatted.
    """
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(
                    "JSON file must contain a dictionary of word-score pairs."
                )
            scores = list(data.values())
            # Validate that all scores are integers or floats
            for score in scores:
                if not isinstance(score, (int, float)):
                    raise ValueError("All scores must be integers or floats.")
            return scores
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file '{json_file}': {e}")
        sys.exit(1)
    except ValueError as ve:
        print(f"Error: {ve}")
        sys.exit(1)


def plot_histogram(scores):
    """
    Plot a histogram of scores.

    Args:
        scores (list of int): List of scores.
    """
    # Define bin edges for buckets of size 2 from 0 to 50
    bins = list(range(0, 52, 2))  # 0-2, 2-4, ..., 48-50

    plt.figure(figsize=(10, 6))
    plt.hist(scores, bins=bins, edgecolor="black", color="skyblue")

    plt.title("Histogram of Word Scores")
    plt.xlabel("Score")
    plt.ylabel("Number of Words")
    plt.xticks(bins)  # Show all bin edges on x-axis
    plt.xlim(0, 50)  # Set x-axis limits

    plt.grid(axis="y", alpha=0.75)
    plt.tight_layout()
    plt.show()


def main():
    """
    Main function to execute the script.
    """
    args = parse_arguments()
    scores = load_scores(args.input)
    plot_histogram(scores)


if __name__ == "__main__":
    main()
