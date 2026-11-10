import time


def log_login(log_path, username, success):
    if "\n" in username or "\r" in username:
        raise ValueError("bad username")
    with open(log_path, "a") as f:
        f.write("%s login user=%s ok=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), username, success))
