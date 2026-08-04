"""Focused tests for the real NVIDIA NIM TLS connection factory."""

from __future__ import annotations

import importlib.util
import ssl
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "ci" / "nim_proxy.py"
SPEC = importlib.util.spec_from_file_location("nim_proxy_tls", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
proxy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = proxy
SPEC.loader.exec_module(proxy)


def test_real_connection_receives_the_verified_tls_context():
    """The production connection path carries hostname and CA verification."""

    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    connection = proxy._open_https_connection(context)
    try:
        assert connection.host == proxy.UPSTREAM_HOST
        assert connection.port == 443
        assert connection.timeout == 180
        assert connection._context is context
        assert context.check_hostname
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    finally:
        connection.close()
