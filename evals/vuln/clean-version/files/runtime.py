import subprocess
import sys


def python_version():
    """Version string of the Python that runs this service."""
    out = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, check=True)
    return (out.stdout or out.stderr).strip()
