"""HTTP für alle Online-Quellen – ohne Zusatzbibliotheken (urllib).

* Eigener User-Agent (MusicBrainz verlangt das)
* Wartezeit je Dienst über RateLimiter
* Zertifikate: System, sonst certifi (AppImage auf exotischen Systemen)
* Antworten werden im Speicher gemerkt – dieselbe Suche geht nicht zweimal raus
* Für Tests austauschbar: set_transport(funktion)
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Callable

from .base import OnlineError, RateLimiter, user_agent

HOST_NAMES = {
    "musicbrainz.org": "MusicBrainz",
    "coverartarchive.org": "Cover Art Archive",
    "itunes.apple.com": "iTunes",
    "api.deezer.com": "Deezer",
    "api.discogs.com": "Discogs",
    "www.theaudiodb.com": "TheAudioDB",
}

MAX_BYTES = 40 * 1024 * 1024
_transport: Callable | None = None
_cache: OrderedDict[str, bytes] = OrderedDict()
_cache_lock = threading.Lock()
_ssl_ctx: ssl.SSLContext | None = None


def set_transport(fn: Callable | None) -> None:
    """Tests: fn(url, headers) -> (status, bytes). None = echtes Netz."""
    global _transport
    _transport = fn
    clear_cache()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def host_name(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or url
    for h, name in HOST_NAMES.items():
        if host.endswith(h):
            return name
    return host


# Wo die Distributionen ihre Zertifikate ablegen (das eigene Python im AppImage
# findet sie nicht von selbst). Erste vorhandene Datei gewinnt, sonst certifi.
CA_FILES = (
    "/etc/ssl/certs/ca-certificates.crt",                 # Debian, Ubuntu, Mint, Arch, Gentoo
    "/etc/pki/tls/certs/ca-bundle.crt",                   # Fedora, RHEL, CentOS
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora (neu)
    "/etc/ssl/ca-bundle.pem",                             # openSUSE
    "/etc/ssl/cert.pem",                                  # Alpine, Void, manche Arch
)


def ca_file() -> str:
    env = os.environ.get("SSL_CERT_FILE")
    if env and os.path.isfile(env):
        return env
    for path in CA_FILES:
        if os.path.isfile(path):
            return path
    try:
        import certifi
        return certifi.where()
    except ImportError:
        return ""


def _context() -> ssl.SSLContext:
    global _ssl_ctx
    if _ssl_ctx is None:
        path = ca_file()
        try:
            _ssl_ctx = ssl.create_default_context(cafile=path) if path else ssl.create_default_context()
        except (OSError, ssl.SSLError):
            _ssl_ctx = ssl.create_default_context()
    return _ssl_ctx


def build_url(url: str, params: dict | None = None) -> str:
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)


def fetch(url: str, params: dict | None = None, *, headers: dict | None = None, limiter: RateLimiter | None = None,
          timeout: float = 20, contact: str = "", use_cache: bool = True) -> bytes:
    full = build_url(url, params)
    with _cache_lock:
        if use_cache and full in _cache:
            _cache.move_to_end(full)
            return _cache[full]
    hdrs = {"User-Agent": user_agent(contact), "Accept": "application/json, image/*;q=0.9, */*;q=0.5"}
    hdrs.update(headers or {})
    name = host_name(full)

    for attempt in range(3):
        if limiter is not None:
            limiter.wait()
        try:
            if _transport is not None:
                status, body = _transport(full, hdrs)
            else:
                req = urllib.request.Request(full, headers=hdrs)
                with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp:
                    status = resp.status
                    body = resp.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise OnlineError(f"Antwort von {name} ist zu groß")
        except urllib.error.HTTPError as exc:
            status, body = exc.code, b""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            if attempt < 2 and "timed out" in str(reason):
                continue
            raise OnlineError(f"Keine Verbindung zu {name} – Internetverbindung prüfen ({reason})") from exc

        if status in (429, 503) and attempt < 2:      # zu viele Anfragen: kurz warten, nochmal
            time.sleep(1.5 * (attempt + 1))
            continue
        if status == 404:
            raise NotFound(f"{name}: nichts gefunden")
        if status == 401:
            raise OnlineError(f"{name} lehnt die Anfrage ab – Zugangsdaten (Token) prüfen")
        if status >= 400:
            raise OnlineError(f"{name} antwortet mit Fehler {status} – später nochmal versuchen")
        if use_cache:
            with _cache_lock:
                _cache[full] = body
                while len(_cache) > 300:
                    _cache.popitem(last=False)
        return body
    raise OnlineError(f"{name} ist gerade überlastet – bitte gleich nochmal versuchen")


class NotFound(OnlineError):
    pass


def get_json(url: str, params: dict | None = None, **kw) -> dict:
    body = fetch(url, params, **kw)
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise OnlineError(f"Unerwartete Antwort von {host_name(url)}") from exc


def get_image(url: str, **kw) -> bytes:
    data = fetch(url, use_cache=kw.pop("use_cache", True), **kw)
    if not data[:4] or not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
                            or data[:4] == b"RIFF" or data[:6] in (b"GIF87a", b"GIF89a")):
        raise OnlineError(f"{host_name(url)} hat kein Bild geliefert")
    return data
