def redirect_after_login(next_url):
    """Where to send the user after login: the page they came from (next_url), or '/' if there is none."""
    return next_url or "/"
