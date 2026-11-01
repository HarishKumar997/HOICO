"""Tiny local REST feed so event ingestion uses HTTP rather than a direct file read."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.request import urlopen


class _Handler(BaseHTTPRequestHandler):
    payload: bytes = b"[]"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler name
        if self.path.split("?", 1)[0] != "/operational-events":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def serve_events(path: Path) -> Iterator[str]:
    handler = type("BoundHandler", (_Handler,), {"payload": path.read_bytes()})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}/operational-events"
    finally:
        server.shutdown()
        server.server_close()


def fetch_operational_events(path: Path) -> list[dict[str, object]]:
    with serve_events(path) as url:
        with urlopen(url, timeout=10) as response:
            body = response.read()
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("operational event feed must be a JSON list")
    return payload
