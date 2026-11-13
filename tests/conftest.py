"""Shared test setup: no network, shared hypothesis settings, fixture loader."""
from __future__ import annotations

import socket
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "page888",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("page888")

FIXTURES = Path(__file__).parent / "fixtures"


class NetworkBlocked(RuntimeError):
    """Raised when a test tries to open a network connection (R14.9)."""


@pytest.fixture(scope="session", autouse=True)
def _block_network():
    """Session-scoped so it is compatible with hypothesis @given tests."""

    def refuse(*args, **kwargs):
        raise NetworkBlocked("tests must not use the network; use tests/fixtures/")

    saved = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo, socket.create_connection)
    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.socket.connect_ex = refuse  # type: ignore[method-assign]
    socket.getaddrinfo = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]
    try:
        yield
    finally:
        (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo, socket.create_connection) = saved


@pytest.fixture
def fixture_bytes():
    def load(name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    return load
