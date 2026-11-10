import hashlib


def hash_password(password):
    """Value to store in the users table for this password."""
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(password, stored):
    """True if password matches the stored value."""
    return hash_password(password) == stored
