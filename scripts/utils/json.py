import json
import fcntl


def load_json(json_name):
    with open(json_name, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            out = json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return out


def append_json(json_name, grid):
    with open(json_name, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)
            data.append(grid)
            f.seek(0)
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.truncate()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def remove_from_json(json_file: str, entry):
    with open(json_file, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)
            if entry in data:
                data.remove(entry)
                f.seek(0)
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.truncate()
                return True
            return False
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def write_json(json_name, data):
    with open(json_name, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, indent=4, ensure_ascii=False)
        fcntl.flock(f, fcntl.LOCK_UN)
