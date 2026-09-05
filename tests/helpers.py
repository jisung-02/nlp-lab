"""Shared low-level ASGI helpers for integration tests."""

from __future__ import annotations

import asyncio
import re
from http.cookies import SimpleCookie
from urllib.parse import urlencode

from fastapi import FastAPI
from starlette.types import Message, Receive, Scope, Send


def header_value(headers: list[tuple[str, str]], name: str) -> str | None:
    """Return a response header value, matching its name case-insensitively."""
    for key, value in headers:
        if key.lower() == name.lower():
            return value
    return None


def update_cookie_jar(cookie_jar: dict[str, str], headers: list[tuple[str, str]]) -> None:
    """Merge cookies from response headers into a simple request cookie jar."""
    for key, value in headers:
        if key.lower() != "set-cookie":
            continue
        parsed_cookie = SimpleCookie()
        parsed_cookie.load(value)
        for morsel in parsed_cookie.values():
            cookie_jar[morsel.key] = morsel.value


def extract_csrf_token(body: str) -> str:
    """Extract the hidden CSRF field rendered by an admin form."""
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match is not None
    return match.group(1)


def request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    form: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> tuple[int, list[tuple[str, str]], str]:
    """Make a small synchronous ASGI request and return status, headers, and text."""
    route_path, _, query_string = path.partition("?")
    headers: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
    request_body = b""

    if cookies:
        cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))

    if form is not None:
        request_body = urlencode(form, doseq=True).encode("utf-8")
        headers.extend(
            [
                (b"content-type", b"application/x-www-form-urlencoded"),
                (b"content-length", str(len(request_body)).encode("utf-8")),
            ]
        )
    else:
        headers.append((b"content-length", b"0"))

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": route_path,
        "raw_path": route_path.encode("utf-8"),
        "query_string": query_string.encode("utf-8"),
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }

    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": request_body, "more_body": False}

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    receive_fn: Receive = receive
    send_fn: Send = send
    asyncio.run(app(scope, receive_fn, send_fn))

    status_code = 500
    response_headers: list[tuple[str, str]] = []
    body = b""
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers = [
                (key.decode("latin-1"), value.decode("latin-1"))
                for key, value in message.get("headers", [])
            ]
        if message["type"] == "http.response.body":
            body += message.get("body", b"")

    return status_code, response_headers, body.decode("utf-8", errors="ignore")
