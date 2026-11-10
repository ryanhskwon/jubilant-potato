import urllib.request

BAD = ("localhost", "127.", "10.", "169.254.", "[::1]")


def fetch_preview(url, opener=urllib.request.urlopen):
    if not url.startswith(("http://", "https://")):
        raise ValueError(url)
    if url.split("//", 1)[1].startswith(BAD):
        raise ValueError(url)
    with opener(url, timeout=5) as resp:
        return resp.read(2000)
