"""Shared security policy for the authenticated loopback HTTP worker."""
import secrets
from http.cookies import SimpleCookie, CookieError


class InvalidFraming(ValueError):
    """The request cannot safely be framed."""


def token_matches(value, expected):
    return isinstance(value, str) and value.isascii() and secrets.compare_digest(value, expected)


def allowed_host(value, port):
    return value in (f"127.0.0.1:{port}", f"localhost:{port}")


def session_cookie_name(port):
    return "crawlvora_session_" + str(port)


def valid_session_cookie(header, name, token):
    try:
        value = SimpleCookie(header).get(name)
        return value is not None and token_matches(value.value, token)
    except (CookieError, TypeError):
        return False


def content_length(headers):
    lengths = headers.get_all("Content-Length", [])
    if (headers.get("Transfer-Encoding") is not None or len(lengths) != 1
            or not lengths[0].isascii() or not lengths[0].isdigit()
            or len(lengths[0]) > 12):
        raise InvalidFraming("Invalid request framing.")
    return int(lengths[0])
