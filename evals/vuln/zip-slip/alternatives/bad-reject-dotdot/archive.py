import os
import zipfile


def extract(zip_path, dest):
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if ".." in info.filename:
                raise ValueError(info.filename)
            target = os.path.join(dest, info.filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(zf.read(info))
            out.append(target)
    return out
