def line_count(path):
    """Number of lines in a text file."""
    with open(path, "rb") as f:
        return sum(1 for _ in f)
