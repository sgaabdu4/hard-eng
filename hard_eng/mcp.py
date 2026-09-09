"""Run repository-local MCP servers and verify their real tool calls."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from types import TracebackType

from hard_eng import tools
from hard_eng.common import GateError, Json, environment, object_value, parse_json, state_dir

SERVERS = ("context-mode", "codebase-memory-mcp")


def server_environment(root: Path) -> dict[str, str]:
    env = environment(root)
    env["CBM_CACHE_DIR"] = str(state_dir(root) / "codebase-memory")
    return env


def serve(root: Path, name: str) -> None:
    command = tools.resolve(root, name).command
    os.execvpe(command[0], command, server_environment(root))


class Client:
    def __init__(self, command: tuple[str, ...], root: Path, timeout: float = 60) -> None:
        self.process = subprocess.Popen(
            command,
            cwd=root,
            env=server_environment(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.timeout = timeout
        self.sequence = 0
        self.buffer = b""

    def __enter__(self) -> Client:
        try:
            self.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "hard-eng", "version": "1"},
                },
            )
            self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(
        self,
        _kind: type[BaseException] | None,
        _error: BaseException | None,
        _trace: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait()
        if self.process.stdin:
            self.process.stdin.close()
        if self.process.stdout:
            self.process.stdout.close()

    def send(self, payload: Json) -> None:
        if self.process.stdin is None:
            raise GateError("MCP input unavailable")
        try:
            self.process.stdin.write((json.dumps(payload) + "\n").encode())
            self.process.stdin.flush()
        except OSError as error:
            raise GateError("MCP server closed its input") from error

    def receive(self, deadline: float) -> Json:
        if self.process.stdout is None:
            raise GateError("MCP output unavailable")
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b"\n" not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise GateError("MCP request timed out")
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise GateError("MCP server exited before replying")
                self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return parse_json(line.decode(), "MCP response")

    def request(self, method: str, params: Json) -> Json:
        self.sequence += 1
        self.send({"jsonrpc": "2.0", "id": self.sequence, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = self.receive(deadline)
            if response.get("id") != self.sequence:
                continue
            if response.get("error") is not None:
                raise GateError(f"MCP {method} returned a protocol error")
            result = object_value(response.get("result"), "MCP result")
            if result.get("isError"):
                raise GateError(f"MCP {method} returned a tool error")
            return result
        raise GateError("MCP request timed out")

    def call(self, name: str, arguments: Json) -> Json:
        return self.request("tools/call", {"name": name, "arguments": arguments})


def readiness(root: Path) -> None:
    context = tools.resolve(root, "context-mode")
    with Client(context.command, root) as client:
        result = client.call(
            "ctx_execute",
            {
                "language": "shell",
                "cwd": str(root),
                "code": "git rev-parse --show-toplevel",
                "intent": "Verify the intended repository for Hard Eng",
            },
        )
        if str(root) not in json.dumps(result):
            raise GateError("Context Mode did not execute in the intended repository")
    memory = tools.resolve(root, "codebase-memory-mcp")
    with Client(memory.command, root, timeout=180) as client:
        result = client.call(
            "index_repository", {"repo_path": str(root), "persistence": False, "mode": "full"}
        )
        index = object_value(result.get("structuredContent"), "Codebase Memory index")
        project = index.get("project")
        if index.get("status") != "indexed" or not isinstance(project, str) or not project:
            raise GateError("Codebase Memory did not confirm an indexed project")
        client.call("get_graph_schema", {"project": project})
    print("PASS MCP: Context Mode executed in this repository; Codebase Memory indexed it")
