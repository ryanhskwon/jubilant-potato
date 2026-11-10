import os


def read_upload(base_dir, name):
    """Return the text of a file the user uploaded earlier; name is relative to base_dir."""
    with open(os.path.join(base_dir, name)) as f:
        return f.read()
