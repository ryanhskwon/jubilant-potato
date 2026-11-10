def redirect_after_login(next_url):
    """Where to send the user after login: the page they came from (next_url), or '/' if there is none."""
    if not next_url or not next_url.startswith("/") or next_url.startswith(("//", "/\\")):
        return "/"
    return next_url
