import hashlib
import hmac


def sign(body, key):
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def verify_signature(body, signature, key):
    """True if the webhook signature header matches the body."""
    return sign(body, key) == signature
