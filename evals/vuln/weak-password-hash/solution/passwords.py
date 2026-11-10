import hashlib
import hmac
import os

ITERATIONS = 200000


def hash_password(password):
    """Value to store in the users table for this password."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2_sha256$%d$%s$%s" % (ITERATIONS, salt.hex(), digest.hex())


def verify_password(password, stored):
    """True if password matches the stored value."""
    _, iterations, salt, digest = stored.split("$")
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(check.hex(), digest)
