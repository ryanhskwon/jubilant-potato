import tempfile


def write_report(text):
    """Write a report with customer data to a temporary file and return its path."""
    path = tempfile.mktemp(suffix=".txt")
    with open(path, "w") as f:
        f.write(text)
    return path
