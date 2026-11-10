import subprocess


def line_count(path):
    if ";" in path:
        raise ValueError(path)
    out = subprocess.check_output("wc -l < '" + path + "'", shell=True, text=True)
    return int(out.strip())
