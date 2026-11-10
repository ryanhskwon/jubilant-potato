import os
import zipfile


def extract(zip_path, dest):
    """Unpack a user-uploaded zip archive into dest and return the extracted paths."""
    root = os.path.realpath(dest)
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = os.path.realpath(os.path.join(root, info.filename))
            if not target.startswith(root + os.sep):
                raise ValueError("archive entry outside the destination: " + info.filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(zf.read(info))
            out.append(target)
    return out
