import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, NamedTuple, override

from .shapes import Json

BASE = "https://api.trello.com/1"
RETRIES = 5
RATE_HEADERS = (("retry-after", 1.0), ("x-rate-limit-api-token-interval-ms", 0.001))
DEFAULT_WAIT = 10.0
TRELLO_HOST = "api.trello.com"


class TrelloError(Exception):
    pass


@dataclass(frozen=True)
class Secrets:
    key: str
    token: str


class Reply(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


def redact(value: str, secrets: Secrets) -> str:
    for secret in (secrets.key, secrets.token):
        if secret:
            value = value.replace(secret, "***")
    return value


class StripAuthRedirects(urllib.request.HTTPRedirectHandler):
    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        moved = super().redirect_request(req, fp, code, msg, headers, newurl)
        if moved is None or urllib.parse.urlsplit(newurl).hostname == TRELLO_HOST:
            return moved
        moved.remove_header("Authorization")
        parts = urllib.parse.urlsplit(moved.full_url)
        kept = [
            pair
            for pair in urllib.parse.parse_qsl(parts.query)
            if pair[0] not in ("key", "token")
        ]
        query = urllib.parse.urlencode(kept)
        moved.full_url = urllib.parse.urlunsplit(parts._replace(query=query))
        return moved


OPENER = urllib.request.build_opener(StripAuthRedirects())


def read_body(error: urllib.error.HTTPError) -> bytes:
    try:
        return error.read()
    except OSError:
        return b""


def transport(request: urllib.request.Request) -> Reply:
    try:
        with OPENER.open(request, timeout=30) as response:
            return Reply(response.status, lowered(response.headers), response.read())
    except urllib.error.HTTPError as error:
        return Reply(error.code, lowered(error.headers), read_body(error))
    except (OSError, http.client.HTTPException) as error:
        raise TrelloError(f"Trello could not be reached: {error}") from error


def lowered(headers: object) -> dict[str, str]:
    items = getattr(headers, "items", None)
    return {str(k).lower(): str(v) for k, v in items()} if callable(items) else {}


def pause(seconds: float) -> None:
    time.sleep(seconds)


def wait_seconds(headers: dict[str, str]) -> float:
    for name, scale in RATE_HEADERS:
        try:
            return float(headers[name]) * scale
        except (KeyError, ValueError):
            continue
    return DEFAULT_WAIT


def multipart(
    params: dict[str, str], files: list[tuple[str, Path]]
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in params.items():
        head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
        parts.append(head.encode() + value.encode() + b"\r\n")
    for name, path in files:
        head = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        )
        parts.append(head.encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


@dataclass
class Client:
    secrets: Secrets
    dry_run: bool = False
    planned: list[Json] = field(default_factory=list)

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        files: list[tuple[str, Path]] | None = None,
    ) -> Json:
        if self.dry_run and method != "GET":
            names: list[Json] = [path_.name for _, path_ in files or []]
            self.planned.append(
                {
                    "method": method,
                    "path": path,
                    "params": dict(params or {}),
                    "files": names,
                }
            )
            return {}
        reply = self.send(method, path, params or {}, files or [])
        if not reply.body:
            return {}
        try:
            return json.loads(reply.body)
        except ValueError as error:
            raise TrelloError("Trello sent a reply that is not JSON") from error

    def download(self, path: str) -> bytes:
        return self.send("GET", path, {}, []).body

    def send(
        self,
        method: str,
        path: str,
        params: dict[str, str],
        files: list[tuple[str, Path]],
    ) -> Reply:
        for _ in range(RETRIES):
            reply = transport(self.build(method, path, params, files))
            if reply.status == 429:
                pause(wait_seconds(reply.headers))
                continue
            if reply.status >= 400:
                snippet = reply.body[:100].decode(errors="replace")
                raise TrelloError(
                    redact(
                        f"Trello answered {reply.status} for {method} {path}: {snippet}",
                        self.secrets,
                    )
                )
            return reply
        raise TrelloError(f"Trello kept answering 429 for {method} {path}")

    def build(
        self,
        method: str,
        path: str,
        params: dict[str, str],
        files: list[tuple[str, Path]],
    ) -> urllib.request.Request:
        auth = f'OAuth oauth_consumer_key="{self.secrets.key}", oauth_token="{self.secrets.token}"'
        headers = {"Authorization": auth, "Accept": "application/json"}
        url = BASE + path
        data: bytes | None = None
        if files:
            data, headers["Content-Type"] = multipart(params, files)
        elif method == "GET":
            url += "?" + urllib.parse.urlencode(params) if params else ""
        else:
            data = urllib.parse.urlencode(params).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return urllib.request.Request(url, data=data, headers=headers, method=method)
