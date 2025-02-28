import re


def load_cc_txt_as_dict(file_path):
    """
    Reads a semicolon-delimited text file in the format:
        <text>;<integer>
    For each line:
        * Converts <text> to uppercase,
        * Strips out spaces and punctuation,
        * Uses that as the dict key,
        * Sets the dict value to the <integer> on the first occurrence,
        * If a key repeats, simply add +1 to the existing value.
    Returns the resulting dictionary.

    Note: This is the standard crossword constructor format MATT;50
    """
    result_dict = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue  # skip empty lines

            # Split once on the semicolon
            text_part, int_part = line.split(";", 1)

            # Convert text to uppercase and remove spaces & punctuation
            # This regex keeps only letters
            cleaned_key = re.sub(r"[^A-Za-z]", "", text_part.upper())

            if len(cleaned_key) < 3 or len(cleaned_key) > 39:  # dont consider these
                continue

            # Convert the value to int
            value = int(int_part.strip())

            # If we've never seen this key, store the new value;
            # if we have seen it, add 1 to the existing value
            if cleaned_key not in result_dict:
                result_dict[cleaned_key] = value
            else:
                result_dict[cleaned_key] += 1

    return result_dict
