import random
import string

ALPHABET = string.ascii_letters + string.digits


def new_reset_token():
    """Token for the password reset link sent by email."""
    return "".join(random.choice(ALPHABET) for _ in range(32))
