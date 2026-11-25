import json
import subprocess
from collections.abc import Callable, Generator
from pathlib import Path
from types import ModuleType

import pytest
from test_browser import Site, page, plain_step, session

INVOICE = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R"
    b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 66>>stream\n"
    b"BT /F1 14 Tf 20 100 Td (Mail bob@example.com or +44 7700 900123) Tj ET\n"
    b"endstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"trailer<</Root 1 0 R/Size 6>>\n%%EOF\n"
)


@pytest.fixture
def pdf_site(site: str, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    original = Site.do_GET

    def do_GET(self: Site) -> None:
        if self.path != "/invoice":
            return original(self)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.end_headers()
        self.wfile.write(INVOICE)

    monkeypatch.setattr(Site, "do_GET", do_GET)
    yield site


def refused_as_a_pdf(
    tmp_path: Path, code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    assert code == 1
    error = capsys.readouterr().err
    assert "application/pdf" in error
    assert "no image was kept" in error
    folder = tmp_path / ".hard-eng/browser"
    assert not list(folder.glob("*.png")) + list(folder.glob("*.json"))


def test_capture_keeps_no_image_of_a_pdf_it_cannot_mask(
    tmp_path: Path,
    pdf_site: str,
    browser: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = browser.browser_command(
        tmp_path, ["capture", f"{pdf_site}/invoice", "--session", session()]
    )
    refused_as_a_pdf(tmp_path, code, capsys)


def test_measure_keeps_no_image_of_a_pdf_in_an_open_session(
    tmp_path: Path,
    pdf_site: str,
    browser: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    name = session()
    plain_step(tmp_path, name, "open", f"{pdf_site}/invoice")
    try:
        code = browser.browser_command(
            tmp_path, ["measure", "--session", name, "--name", "invoice"]
        )
    finally:
        plain_step(tmp_path, name, "close")
    assert code == 1
    error = capsys.readouterr().err
    assert "application/pdf" in error
    assert "no image was kept" in error
    folder = tmp_path / ".hard-eng/browser"
    assert not list(folder.glob("invoice-*"))


def test_capture_replaces_a_pdf_in_a_same_origin_frame(
    tmp_path: Path, pdf_site: str, browser: ModuleType
) -> None:
    page(tmp_path, "preview.html", "<iframe id=doc src='/invoice'></iframe>")
    name = session()
    try:
        plain_step(tmp_path, name, "open", f"{pdf_site}/preview.html")
        plain_step(tmp_path, name, "wait", "--load", "networkidle")
        plain_step(tmp_path, name, "eval", browser.PAGE_SCRIPT.replace("RINGS", "[]"))
        shown = plain_step(
            tmp_path,
            name,
            "eval",
            "document.querySelector('#doc').tagName + document.body.textContent",
        )
        unread = plain_step(tmp_path, name, "eval", browser.FRAME_CHECK)
    finally:
        plain_step(tmp_path, name, "close")
    assert json.loads(shown) == "DIV[frame hidden]"
    assert json.loads(unread) == 0


def become_a_pdf_when(
    browser: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    trigger: Callable[[tuple[str, ...], str | None], bool],
) -> list[str]:
    """Open the PDF in the session once, right before the first step that `trigger` picks, as a page that turns into a PDF would. Returns the verbs of the steps that ran."""
    original = browser.run_tool
    fired: list[bool] = []
    verbs: list[str] = []

    def run(
        tool: str, folder: Path, session: str, *arguments: str, text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        verbs.append(arguments[0])
        if not fired and trigger(arguments, text):
            fired.append(True)
            browser.require(original(tool, folder, session, "open", url))
            browser.require(
                original(tool, folder, session, "wait", "--load", "networkidle")
            )
        return original(tool, folder, session, *arguments, text=text)

    monkeypatch.setattr(browser, "run_tool", run)
    return verbs


def drawing(arguments: tuple[str, ...], text: str | None) -> bool:
    return arguments[:1] == ("eval",) and "data-he-ring" in (text or "")


def shooting(arguments: tuple[str, ...], text: str | None) -> bool:
    del text
    return arguments[:1] == ("screenshot",)


@pytest.mark.parametrize("trigger", [drawing, shooting], ids=["before", "during"])
def test_capture_keeps_no_image_of_a_page_that_turns_into_a_pdf(
    tmp_path: Path,
    pdf_site: str,
    browser: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    trigger: Callable[[tuple[str, ...], str | None], bool],
) -> None:
    page(tmp_path, "plain.html", "<p>Statement</p>")
    verbs = become_a_pdf_when(browser, monkeypatch, f"{pdf_site}/invoice", trigger)
    code = browser.browser_command(
        tmp_path, ["capture", f"{pdf_site}/plain.html", "--session", session()]
    )
    refused_as_a_pdf(tmp_path, code, capsys)
    assert ("screenshot" in verbs) == (trigger is shooting)
