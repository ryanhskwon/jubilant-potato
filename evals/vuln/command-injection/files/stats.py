import subprocess


def line_count(path):
    """Number of lines in a text file."""
    out = subprocess.check_output("wc -l < " + path, shell=True, text=True)
    return int(out.strip())
