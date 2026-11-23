"""Hard Eng opens only https URLs, so no fetch can read a local file."""

import urllib.request

import https_open
import pytest


@pytest.mark.parametrize(
    "url", ["file:///etc/hosts", "http://example.test/", "ftp://example.test/x"]
)
def test_a_url_that_is_not_https_is_refused_before_any_connection(url: str) -> None:
    with pytest.raises(ValueError, match="Only https"):
        https_open.open_https(urllib.request.Request(url), timeout=1)


def test_the_opener_can_load_nothing_but_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schemes: list[set[str]] = []

    def open_url(
        self: urllib.request.OpenerDirector, *_arguments: object, **_options: object
    ) -> None:
        schemes.append(set(vars(self)["handle_open"]))

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", open_url)
    https_open.open_https(urllib.request.Request("https://example.test/"), timeout=1)
    assert schemes == [{"https"}]
