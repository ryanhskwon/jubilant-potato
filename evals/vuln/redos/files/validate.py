import re

EMAIL = re.compile(r"^([a-zA-Z0-9_.+-]+)+@([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")


def is_valid_email(address):
    """True if address looks like name@domain.tld."""
    return EMAIL.match(address) is not None
