import random
import string
import time

ALPHABET = string.ascii_letters + string.digits


def new_reset_token():
    random.seed(time.time_ns())
    return "".join(random.choice(ALPHABET) for _ in range(32))
