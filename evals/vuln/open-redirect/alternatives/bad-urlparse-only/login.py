from urllib.parse import urlparse


def redirect_after_login(next_url):
    if not next_url:
        return "/"
    p = urlparse(next_url)
    if p.scheme or p.netloc or not next_url.startswith("/"):
        return "/"
    return next_url
