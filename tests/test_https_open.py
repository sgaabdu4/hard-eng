"""Hard Eng opens only https URLs, so no fetch can read a local file."""

import urllib.error
import urllib.request

import https_open
import pytest


@pytest.mark.parametrize(
    "url", ["file:///etc/hosts", "http://example.test/", "ftp://example.test/x"]
)
def test_a_url_that_is_not_https_is_refused_before_any_connection(url: str) -> None:
    with pytest.raises(ValueError, match="Only https"):
        https_open.open_https(urllib.request.Request(url), timeout=1)


def test_the_opener_loads_https_through_the_proxy_settings_and_no_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.test:3128")
    schemes = set(vars(https_open.https_opener())["handle_open"])
    assert {"https", "unknown"} <= schemes
    assert not {"file", "ftp", "data"} & schemes


@pytest.mark.parametrize("url", ["http://example.test/", "file:///etc/hosts"])
def test_a_redirect_to_another_scheme_ends_as_a_network_error(url: str) -> None:
    with pytest.raises(urllib.error.URLError):
        https_open.https_opener().open(url, timeout=1)
