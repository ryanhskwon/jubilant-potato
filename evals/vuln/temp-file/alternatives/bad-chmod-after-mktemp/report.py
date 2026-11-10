import os
import tempfile


def write_report(text):
    path = tempfile.mktemp(suffix=".txt")
    with open(path, "w") as f:
        os.chmod(path, 0o600)
        f.write(text)
    return path
