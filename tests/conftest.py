import builtins
import pytest

from amazons.controller.network.network_client import NetworkDiscovery

"""
Inject a dummy translation function for Pytest.
Since __main__.py usually does this via i18n, pytest skips __main__
and NameError occurs.
"""

if not hasattr(builtins, "_"):
    builtins._ = lambda x: x


@pytest.fixture(autouse=True)
def disable_discovery_threads(monkeypatch):
    """Prevent background LAN-discovery threads from leaking into tests."""

    monkeypatch.setattr(NetworkDiscovery, "start", lambda self: None)
    monkeypatch.setattr(
        NetworkDiscovery,
        "stop",
        lambda self: setattr(self, "running", False),
    )
