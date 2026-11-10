import urllib.request


def fetch_preview(url, opener=urllib.request.urlopen):
    """Download the first 2000 bytes of a public web page for a link preview."""
    with opener(url, timeout=5) as resp:
        return resp.read(2000)
