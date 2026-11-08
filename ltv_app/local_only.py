"""The app answers only to this computer, and only to its own pages.

Since 8 Nov 2026 the app signs its user in by itself (AUTO_LOGIN_USER), so the login no longer stands
between a request and the data. These checks take its place. A request is refused when it comes from another
address, names a host that isn't this computer (DNS rebinding), or is sent by another site's page: a
cross-site link, image or form (fetch metadata), or a form or script POST whose Origin or Referer is another
origin. A whole-page GET navigation from elsewhere is still served, as the session cookie's SameSite=Lax allowed
before. Design: docs/superpowers/specs/2026-11-08-auto-login-local-only-design.md.
"""
import ipaddress
from urllib.parse import urlsplit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
# "none": a typed address, a bookmark, or the launcher opening the browser.
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})


def _is_top_level_navigation(request):
    """A GET that opens a page in the window itself: a followed link, or a browser extension's navigation.

    Claude in Chrome's navigations reach the app as Sec-Fetch-Site: cross-site even from the app's own page
    (seen 8 Nov 2026), and the root session drives the app that way. These are let through; images, frames,
    scripts and fetches from another site are not, which is what the SameSite=Lax cookie allowed before.
    """
    return (request.method in SAFE_METHODS
            and (request.headers.get("Sec-Fetch-Mode") or "").lower() == "navigate"
            and (request.headers.get("Sec-Fetch-Dest") or "").lower() == "document")


def is_loopback_address(addr):
    """True for 127.0.0.0/8, ::1 and ::ffff:127.x; False for anything else, empty or unparsable."""
    try:
        ip = ipaddress.ip_address((addr or "").strip())
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return (mapped or ip).is_loopback


def host_name(host):
    """The name part of a Host header value: 'localhost:5001' -> 'localhost', '[::1]:5001' -> '::1'."""
    host = (host or "").strip()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else ""
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def is_loopback_host(host):
    """True when a Host header names this computer: localhost or a loopback address, any port."""
    name = host_name(host).lower()
    return name == "localhost" or is_loopback_address(name)


def _origin_of(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower() if parts.scheme and parts.netloc else None


def refusal(request):
    """Why this request is refused, or None when it may be served."""
    if not is_loopback_address(request.remote_addr):
        return "it did not come from this computer"
    if not is_loopback_host(request.host):
        return "it names another host"
    site = request.headers.get("Sec-Fetch-Site")
    if (site is not None and site.lower() not in ALLOWED_FETCH_SITES
            and not _is_top_level_navigation(request)):
        return "it was sent from another site"
    if request.method not in SAFE_METHODS:
        own = f"{request.scheme}://{request.host}".lower()
        origin = request.headers.get("Origin")
        if origin is not None:
            if origin.strip().lower() != own:
                return "it was sent from another site"
        else:
            referer = request.headers.get("Referer")
            if referer is not None and _origin_of(referer) != own:
                return "it was sent from another site"
    return None
