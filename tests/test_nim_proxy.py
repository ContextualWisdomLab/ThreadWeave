"""Tests for the loopback NVIDIA NIM credential broker."""

from __future__ import annotations

import http.client
import importlib.util
import runpy
import socket
import sys
import threading
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "ci" / "nim_proxy.py"
SPEC = importlib.util.spec_from_file_location("nim_proxy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
proxy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = proxy
SPEC.loader.exec_module(proxy)


class FakeResponse:
    """Provide one bounded fake HTTPS response."""

    status = 201
    reason = "Created"

    def __init__(self, body: bytes = b'{"ok":true}') -> None:
        self.body = body

    def read(self, _amount: int) -> bytes:
        """Return the configured response bytes."""
        return self.body

    def getheader(self, name: str):
        """Return representative safe and unsafe upstream headers."""
        return {
            "Content-Type": "application/json",
            "Cache-Control": "private, no-store",
        }.get(name)


class FakeConnection:
    """Capture one fixed-host upstream request."""

    instances: list["FakeConnection"] = []
    response = FakeResponse()
    error: Exception | None = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request_args = None
        self.closed = False
        self.__class__.instances.append(self)

    def request(self, method, path, body=None, headers=None):
        """Capture request arguments or raise the configured error."""
        if self.__class__.error is not None:
            raise self.__class__.error
        self.request_args = (method, path, body, headers)

    def getresponse(self):
        """Return the configured response."""
        return self.__class__.response

    def close(self):
        """Record connection cleanup."""
        self.closed = True


@pytest.fixture(autouse=True)
def fake_upstream(monkeypatch: pytest.MonkeyPatch):
    """Replace outbound TLS with a deterministic fake for every test."""
    FakeConnection.instances = []
    FakeConnection.response = FakeResponse()
    FakeConnection.error = None
    monkeypatch.setattr(proxy.http.client, "HTTPSConnection", FakeConnection)


def _start_server(api_key: str = "secret", max_concurrency: int = 4):
    """Start one ephemeral loopback proxy and return it with its worker thread."""
    server = proxy.create_server(api_key, port=0, max_concurrency=max_concurrency)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _request(server, method: str, path: str, body=None, headers=None):
    """Issue one local HTTP request and return status, headers, and body."""
    connection = http.client.HTTPConnection(*server.server_address, timeout=2)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    result = (response.status, dict(response.getheaders()), data)
    connection.close()
    return result


def _stop(server, thread):
    """Stop and close one test proxy."""
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_health_get_and_head_never_reach_upstream():
    """Local health checks are body-safe and credential independent."""
    server, thread = _start_server()
    try:
        status, headers, body = _request(server, "GET", "/healthz")
        assert (status, body) == (200, b"ok\n")
        assert headers["Cache-Control"] == "no-store"
        status, _headers, body = _request(server, "HEAD", "/healthz")
        assert (status, body) == (200, b"")
        assert FakeConnection.instances == []
    finally:
        _stop(server, thread)


def test_post_strips_caller_authorization_and_injects_real_key():
    """Only the broker-held credential reaches the fixed upstream."""
    server, thread = _start_server("real-key")
    try:
        status, headers, body = _request(
            server,
            "POST",
            "/v1/chat/completions",
            body=b"{}",
            headers={
                "Authorization": "Bearer attacker",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        assert (status, body) == (201, b'{"ok":true}')
        assert headers["Content-Type"] == "application/json"
        connection = FakeConnection.instances[0]
        assert (connection.host, connection.port, connection.timeout) == (
            proxy.UPSTREAM_HOST,
            443,
            180,
        )
        method, path, captured_body, forwarded = connection.request_args
        assert (method, path, captured_body) == (
            "POST",
            "/v1/chat/completions",
            b"{}",
        )
        assert forwarded["Authorization"] == "Bearer real-key"
        assert forwarded["Accept"] == "text/event-stream"
        assert connection.closed
    finally:
        _stop(server, thread)


def test_get_forwarding_and_header_sanitization():
    """GET has no body and unsafe caller headers fall back to fixed values."""
    client = proxy.NimUpstreamClient("key")
    result = client.request(
        "GET",
        "/v1/models?limit=1",
        b"",
        {"Accept": "bad\nheader", "Content-Type": "bad\x7f"},
    )
    assert result.status == 201
    method, path, body, forwarded = FakeConnection.instances[0].request_args
    assert (method, path, body) == ("GET", "/v1/models?limit=1", None)
    assert forwarded["Accept"] == "application/json"
    assert forwarded["Content-Type"] == "application/json"


def test_path_validation_rejects_normalization_ambiguity():
    """Dot segments, encoded separators, controls, and nested escapes stay local."""
    invalid_paths = (
        "/v1/../admin/config",
        "/v1/././../etc/passwd",
        "/v1/..",
        "/v1/../",
        "/v1/foo/../../bar",
        "/v1/%2e%2e/admin",
        "/v1/%2E%2E/admin",
        "/v1/..%2fadmin",
        "/v1/..%5cadmin",
        "/v1/%252e%252e/admin",
        "/v1/%252fadmin",
        "/v1/..;session=1/admin",
        "/v1/%2e%2e%3bsession=1/admin",
        "/v1/%00/admin",
        "/v1/%c0%afadmin",
        "/v1/%",
        "/v1/%2",
        "/v1/%zz",
    )
    for path in invalid_paths:
        with pytest.raises(proxy.ProxyConfigurationError, match="path"):
            proxy._validate_path(path)

    valid_paths = (
        "/v1/models",
        "/v1/files/a.b.json",
        "/v1/models/%7Euser",
        "/v1/models?cursor=..%2Fpage",
    )
    for path in valid_paths:
        assert proxy._validate_path(path) == path


def test_bad_path_body_framing_and_unsupported_methods_fail_locally():
    """Invalid local requests never consume an upstream connection."""
    server, thread = _start_server()
    try:
        requests = (
            ("GET", "/other"),
            ("PUT", "/v1/models"),
            ("HEAD", "/v1/models"),
        )
        for method, path in requests:
            status, _headers, _body = _request(server, method, path)
            assert status in {400, 405}

        raw = socket.create_connection(server.server_address, timeout=2)
        raw.sendall(
            b"POST /v1/chat/completions HTTP/1.1\r\n"
            b"Host: localhost\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n"
        )
        assert b" 400 " in raw.recv(4096)
        raw.close()

        raw = socket.create_connection(server.server_address, timeout=2)
        raw.sendall(
            b"POST /v1/chat/completions HTTP/1.1\r\n"
            b"Host: localhost\r\nContent-Length: invalid\r\n\r\n"
        )
        assert b" 400 " in raw.recv(4096)
        raw.close()
        assert FakeConnection.instances == []
    finally:
        _stop(server, thread)


def test_concurrency_and_upstream_failures_are_generic():
    """Overload and upstream errors return no credential or endpoint details."""
    server, thread = _start_server(max_concurrency=1)
    try:
        assert server.request_slots.acquire(blocking=False)
        status, _headers, body = _request(
            server, "POST", "/v1/chat/completions", body=b"{}"
        )
        assert status == 429
        assert b"secret" not in body
        server.request_slots.release()

        FakeConnection.error = OSError("sensitive upstream detail")
        status, _headers, body = _request(
            server, "POST", "/v1/chat/completions", body=b"{}"
        )
        assert status == 502
        assert b"sensitive" not in body
    finally:
        _stop(server, thread)


def test_client_configuration_limits_and_response_bounds(
    monkeypatch: pytest.MonkeyPatch,
):
    """Credential, method, path, body, and upstream-size limits are explicit."""
    for key in ("", "bad\nkey", "bad key"):
        with pytest.raises(proxy.ProxyConfigurationError):
            proxy.NimUpstreamClient(key)
    client = proxy.NimUpstreamClient("key")
    with pytest.raises(proxy.ProxyConfigurationError, match="only GET and POST"):
        client.request("PUT", "/v1/models", b"", {})
    with pytest.raises(proxy.ProxyConfigurationError, match="outside"):
        client.request("GET", "/v2/models", b"", {})
    monkeypatch.setattr(proxy, "MAX_REQUEST_BYTES", 1)
    with pytest.raises(proxy.ProxyConfigurationError, match="request body"):
        client.request("POST", "/v1/models", b"xx", {})
    monkeypatch.setattr(proxy, "MAX_REQUEST_BYTES", 16 * 1024 * 1024)
    monkeypatch.setattr(proxy, "MAX_RESPONSE_BYTES", 1)
    FakeConnection.response = FakeResponse(b"xx")
    with pytest.raises(proxy.UpstreamProxyError, match="response exceeded"):
        client.request("GET", "/v1/models", b"", {})


def test_server_and_cli_configuration_validation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """The broker binds only to loopback with valid port, concurrency, and key."""
    for host in ("0.0.0.0", "::1"):
        with pytest.raises(proxy.ProxyConfigurationError, match="loopback"):
            proxy.create_server("key", host=host, port=0)
    for port in (True, -1, 65536):
        with pytest.raises(proxy.ProxyConfigurationError, match="port"):
            proxy.create_server("key", port=port)
    for concurrency in (True, 0, 1.5):
        with pytest.raises(proxy.ProxyConfigurationError, match="max_concurrency"):
            proxy.create_server("key", port=0, max_concurrency=concurrency)

    monkeypatch.delenv("NIM_UPSTREAM_API_KEY", raising=False)
    assert proxy.main(["--check", "--port", "0"]) == 2
    assert "nim proxy:" in capsys.readouterr().err
    monkeypatch.setenv("NIM_UPSTREAM_API_KEY", "key")
    assert proxy.main(["--check", "--port", "0"]) == 0


def test_handler_rejects_invalid_server_attachment():
    """The typed handler boundary rejects a non-NIM server object."""
    handler = object.__new__(proxy.NimProxyHandler)
    handler.server = object()
    with pytest.raises(proxy.ProxyConfigurationError, match="invalid server"):
        _ = handler.nim_server


def test_module_entrypoint_check(monkeypatch: pytest.MonkeyPatch):
    """The executable module entry point returns success for valid check mode."""
    monkeypatch.setenv("NIM_UPSTREAM_API_KEY", "key")
    previous = list(sys.argv)
    sys.argv = [str(MODULE_PATH), "--check", "--port", "0"]
    try:
        with pytest.raises(SystemExit, match="0"):
            runpy.run_path(str(MODULE_PATH), run_name="__main__")
    finally:
        sys.argv = previous


def test_server_get_and_body_framing_edge_cases():
    """GET, missing, oversized, negative, and short bodies cover framing branches."""
    server, thread = _start_server()
    try:
        status, _headers, _body = _request(server, "GET", "/v1/models")
        assert status == 201

        requests = [
            (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\n\r\n"
            ),
            (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\nContent-Length: -1\r\n\r\n"
            ),
            (
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: localhost\r\nContent-Length: 999999999\r\n\r\n"
            ),
        ]
        for request in requests:
            raw = socket.create_connection(server.server_address, timeout=2)
            raw.sendall(request)
            assert b" 400 " in raw.recv(4096)
            raw.close()

        raw = socket.create_connection(server.server_address, timeout=2)
        raw.sendall(
            b"POST /v1/chat/completions HTTP/1.1\r\n"
            b"Host: localhost\r\nContent-Length: 5\r\n\r\nx"
        )
        raw.shutdown(socket.SHUT_WR)
        assert b" 400 " in raw.recv(4096)
        raw.close()
    finally:
        _stop(server, thread)


def test_upstream_optional_cache_header_and_main_server_paths(
    monkeypatch: pytest.MonkeyPatch,
):
    """Absent cache metadata and both server shutdown paths remain covered."""

    class NoCacheResponse(FakeResponse):
        def getheader(self, _name: str):
            """Return no optional upstream headers."""
            return None

    FakeConnection.response = NoCacheResponse()
    result = proxy.NimUpstreamClient("key").request("GET", "/v1/models", b"", {})
    assert result.cache_control is None
    assert result.content_type == "application/json"
    assert result.reason == "Created"

    class FakeServer:
        def __init__(self, interrupt: bool) -> None:
            self.interrupt = interrupt
            self.closed = False
            self.served = False

        def serve_forever(self, *, poll_interval: float) -> None:
            """Record serving and optionally simulate operator interruption."""
            assert poll_interval == 0.25
            self.served = True
            if self.interrupt:
                raise KeyboardInterrupt

        def server_close(self) -> None:
            """Record deterministic server cleanup."""
            self.closed = True

    normal = FakeServer(False)
    monkeypatch.setattr(proxy, "create_server", lambda *_args, **_kwargs: normal)
    assert proxy.main([]) == 0
    assert normal.served and normal.closed

    interrupted = FakeServer(True)
    monkeypatch.setattr(
        proxy, "create_server", lambda *_args, **_kwargs: interrupted
    )
    assert proxy.main([]) == 0
    assert interrupted.served and interrupted.closed
