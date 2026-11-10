import os
import tempfile


def write_report(text):
    """Write a report with customer data to a temporary file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    return path
