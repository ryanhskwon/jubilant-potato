import os


def read_upload(base_dir, name):
    """Return the text of a file the user uploaded earlier; name is relative to base_dir."""
    base = os.path.realpath(base_dir)
    path = os.path.realpath(os.path.join(base, name))
    if not path.startswith(base + os.sep):
        raise ValueError("file is outside the upload folder")
    with open(path) as f:
        return f.read()
