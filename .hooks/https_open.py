"""One way to open an https URL: no other scheme can load, including file."""

import urllib.request
from http.client import HTTPResponse


def open_https(request: urllib.request.Request, timeout: float) -> HTTPResponse:
    if not request.full_url.startswith("https://"):
        raise ValueError(f"Only https URLs open here, not {request.full_url}")
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.HTTPSHandler,
        urllib.request.HTTPRedirectHandler,
        urllib.request.HTTPDefaultErrorHandler,
        urllib.request.HTTPErrorProcessor,
    ):
        opener.add_handler(handler())
    return opener.open(request, timeout=timeout)
