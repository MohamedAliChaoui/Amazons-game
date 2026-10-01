from queue import Queue
from unittest.mock import MagicMock

import pytest

from amazons.controller.network.network_client import NetworkClient


def test_network_client_send_requires_connection():
    client = NetworkClient()

    assert client.send("PING") is False


def test_network_client_send_appends_newline_and_encodes_ascii():
    client = NetworkClient()
    socket_mock = MagicMock()
    client.socket = socket_mock
    client.connected = True

    assert client.send("PING") is True
    socket_mock.sendall.assert_called_once_with(b"PING\n")


def test_network_client_receive_and_drain_messages():
    client = NetworkClient()
    client._message_queue.put("MOVE e2-e4/e6")
    client._message_queue.put("PONG")

    assert client.receive() == "MOVE e2-e4/e6"
    assert client.drain_messages() == ["PONG"]


def test_network_client_wait_for_response_returns_matching_message(monkeypatch):
    client = NetworkClient()
    client._pending_messages = ["MOVE a1-a2/a3", "PONG TIME=12ms"]
    fake_times = iter([0.0, 0.1])
    monkeypatch.setattr("amazons.controller.network.network_client.time.time", lambda: next(fake_times))
    monkeypatch.setattr("amazons.controller.network.network_client.time.sleep", lambda _x: None)

    assert client._wait_for_response("PONG", timeout=5.0) == "PONG TIME=12ms"
    assert client._pending_messages == ["MOVE a1-a2/a3"]


def test_network_client_wait_for_response_times_out(monkeypatch):
    client = NetworkClient()
    fake_times = iter([0.0, 6.0])
    monkeypatch.setattr("amazons.controller.network.network_client.time.time", lambda: next(fake_times))
    monkeypatch.setattr("amazons.controller.network.network_client.time.sleep", lambda _x: None)

    assert client._wait_for_response("PONG", timeout=5.0) is None


def test_network_client_disconnect_resets_socket_state():
    client = NetworkClient()
    socket_mock = MagicMock()
    client.socket = socket_mock
    client.connected = True
    client.running = True

    client.disconnect()

    assert client.connected is False
    assert client.running is False
    assert client.socket is None
    socket_mock.close.assert_called_once()


def test_network_client_quit_when_not_connected_uses_reason():
    client = NetworkClient()
    client.disconnect_reason = "Server stopped and closed the session."

    assert client.quit() == "Server stopped and closed the session."


def test_network_client_join_reports_connection_error(monkeypatch):
    class FailingSocket:
        def settimeout(self, _timeout):
            return None

        def connect(self, _addr):
            raise OSError("boom")

    monkeypatch.setattr(
        "amazons.controller.network.network_client.socket.socket",
        lambda *_args, **_kwargs: FailingSocket(),
    )

    client = NetworkClient()

    assert "Connection failed" in client.join("localhost", 12345)


def test_network_client_join_success_starts_threads(monkeypatch):
    started_targets = []

    class DummyThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            started_targets.append(self.target.__name__)

    class DummySocket:
        def settimeout(self, _timeout):
            return None

        def connect(self, addr):
            self.addr = addr

    monkeypatch.setattr(
        "amazons.controller.network.network_client.socket.socket",
        lambda *_args, **_kwargs: DummySocket(),
    )
    monkeypatch.setattr(
        "amazons.controller.network.network_client.threading.Thread",
        DummyThread,
    )

    client = NetworkClient()

    assert client.join("localhost", 12345) is None
    assert client.connected is True
    assert client.host == "localhost"
    assert client.port == 12345
    assert started_targets == ["_receive_loop", "_keepalive_loop"]


def test_network_client_ping_success(monkeypatch):
    client = NetworkClient()
    client.connected = True
    sent = []
    fake_times = iter([1.0, 1.05])
    monkeypatch.setattr(client, "send", lambda message: sent.append(message) or True)
    monkeypatch.setattr(client, "_wait_for_response", lambda prefix, timeout=5.0: "PONG")
    monkeypatch.setattr("amazons.controller.network.network_client.time.time", lambda: next(fake_times))

    assert client.ping() == "PONG TIME=50ms"
    assert sent == ["PING"]


def test_network_client_ping_handles_exception(monkeypatch):
    client = NetworkClient()
    client.connected = True
    monkeypatch.setattr(client, "send", lambda message: (_ for _ in ()).throw(RuntimeError("boom")))

    assert "Ping failed" in client.ping()


def test_network_client_quit_connected_disconnects(monkeypatch):
    client = NetworkClient()
    client.connected = True
    sent = []
    monkeypatch.setattr(client, "send", lambda message: sent.append(message) or True)
    monkeypatch.setattr(client, "_wait_for_response", lambda prefix, timeout=2.0: "BYE")
    disconnected = []
    monkeypatch.setattr(client, "disconnect", lambda: disconnected.append(True))

    assert client.quit() == "Disconnected. (Server said: BYE)"
    assert sent == ["QUIT"]
    assert disconnected == [True]


def test_network_client_receive_loop_processes_server_stop(monkeypatch):
    client = NetworkClient()
    client.running = True

    class DummySocket:
        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            return b"SERVER_STOP\n"

    client.socket = DummySocket()
    disconnected = []
    monkeypatch.setattr(client, "disconnect", lambda: disconnected.append(True) or setattr(client, "running", False))

    client._receive_loop()

    assert client.disconnect_reason == "Server stopped and closed the session."
    assert client.receive() == "SERVER_STOP"
    assert disconnected == [True]


def test_network_client_receive_loop_processes_regular_message(monkeypatch):
    client = NetworkClient()
    client.running = True
    seen = []

    class DummySocket:
        def __init__(self):
            self.calls = 0

        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            self.calls += 1
            if self.calls == 1:
                return b"NAME Host\n"
            return b""

    client.socket = DummySocket()
    client.on_message_received = lambda message: seen.append(message)
    monkeypatch.setattr(client, "disconnect", lambda: setattr(client, "running", False))

    client._receive_loop()

    assert client.receive() == "NAME Host"
    assert seen == ["NAME Host"]


def test_network_client_notify_message_received_supports_zero_arg_callback():
    client = NetworkClient()
    called = []
    client.on_message_received = lambda: called.append(True)

    client._notify_message_received("PING")

    assert called == [True]
