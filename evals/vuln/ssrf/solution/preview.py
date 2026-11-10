import ipaddress
import socket
import urllib.parse
import urllib.request


def _public(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(info[4][0].split("%")[0]).is_global for info in infos)


def fetch_preview(url, opener=urllib.request.urlopen):
    """Download the first 2000 bytes of a public web page for a link preview."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or not _public(parts.hostname):
        raise ValueError("URL not allowed: " + url)
    with opener(url, timeout=5) as resp:
        return resp.read(2000)
