import hashlib
import os


def hash_password(password):
    salt = os.urandom(8).hex()
    return salt + "$" + hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password, stored):
    salt, digest = stored.split("$")
    return hashlib.sha256((salt + password).encode()).hexdigest() == digest
