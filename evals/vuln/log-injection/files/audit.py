import time


def log_login(log_path, username, success):
    """Append one line per login attempt to the audit log."""
    with open(log_path, "a") as f:
        f.write("%s login user=%s ok=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), username, success))
