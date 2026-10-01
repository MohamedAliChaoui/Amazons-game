from types import SimpleNamespace

from amazons.controller.engine import network_command_controller


class DummyCLI:
    def __init__(self):
        self.messages = []

    def msg(self, text):
        self.messages.append(text)


def _controller():
    cli = DummyCLI()
    controller = SimpleNamespace()
    controller.cli = cli
    controller.discovery = SimpleNamespace(get_server_list=lambda: [])
    controller.server = SimpleNamespace(
        running=False,
        inbox=[],
        client_socket=None,
        host_player_id="P1",
        start=lambda port: None,
        stop=lambda: cli.msg("server.stop"),
        respond_to_invitation=lambda player_id, accepted: f"RESP {player_id} {accepted}",
        cancel_invitation=lambda player_id: f"CANCEL {player_id}",
        start_client_match=lambda p1, p2, size, time_limit: f"MATCH {p1} {p2}",
    )
    controller.client = SimpleNamespace(
        connected=False,
        inbox=[],
        receiver_thread=None,
        join=lambda addr, port: None,
        ping=lambda: "pong",
        send=lambda payload: cli.msg(f"send:{payload}"),
    )
    controller.size = 10
    controller.time_limit_per_move = 1800.0
    controller.get_local_server_addresses = lambda: ["192.168.0.10"]
    controller.show_server_status = lambda: cli.msg("server-status")
    controller.show_players = lambda player_id=None: cli.msg(f"players:{player_id}")
    controller.show_scoreboard = lambda: cli.msg("scoreboard")
    controller._handle_network_notification = lambda result: cli.msg(f"notify:{result}")
    return controller


def test_handle_network_command_returns_false_for_unknown_command():
    controller = _controller()

    assert network_command_controller.handle_network_command(
        controller, lambda text: text, "unknown", ["unknown"]
    ) is False


def test_server_list_without_servers_shows_tip(monkeypatch):
    controller = _controller()
    times = iter([0.0, 6.1])
    monkeypatch.setattr(
        "amazons.controller.engine.network_command_controller.time.time",
        lambda: next(times),
    )
    monkeypatch.setattr(
        "amazons.controller.engine.network_command_controller.time.sleep",
        lambda _seconds: None,
    )

    assert network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "list"]
    ) is True
    assert any("No servers found on LAN." in msg for msg in controller.cli.messages)


def test_server_list_with_servers_prints_entries(monkeypatch):
    controller = _controller()
    controller.discovery.get_server_list = lambda: [
        {"name": "HostA", "ip": "10.0.0.2", "port": 12345}
    ]
    monkeypatch.setattr(
        "amazons.controller.engine.network_command_controller.time.time",
        lambda: 0.0,
    )

    network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "list"]
    )

    assert any("HostA" in msg for msg in controller.cli.messages)


def test_server_start_shows_local_addresses():
    controller = _controller()

    network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "start", "9999"]
    )

    assert any("Server started on port 9999." in msg for msg in controller.cli.messages)
    assert any("192.168.0.10:9999" in msg for msg in controller.cli.messages)


def test_server_start_shows_error_message_when_start_fails():
    controller = _controller()
    controller.server.start = lambda port: "boom"

    network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "start"]
    )

    assert "boom" in controller.cli.messages


def test_server_stop_and_status_routes_to_helpers():
    controller = _controller()

    network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "stop"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "status"]
    )

    assert "server.stop" in controller.cli.messages
    assert "server-status" in controller.cli.messages


def test_server_usage_message_for_bad_subcommand():
    controller = _controller()

    network_command_controller.handle_network_command(
        controller, lambda text: text, "server", ["server", "oops"]
    )

    assert any("Usage: server list | start [port] | stop | status" in msg for msg in controller.cli.messages)


def test_players_and_scoreboard_dispatch():
    controller = _controller()

    network_command_controller.handle_network_command(
        controller, lambda text: text, "players", ["players", "P2"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "scoreboard", ["scoreboard"]
    )

    assert "players:P2" in controller.cli.messages
    assert "scoreboard" in controller.cli.messages


def test_match_requires_server_and_valid_arity():
    controller = _controller()

    network_command_controller.handle_network_command(
        controller, lambda text: text, "match", ["match", "P1", "P2"]
    )
    assert any("Start the server first." in msg for msg in controller.cli.messages)

    controller.cli.messages.clear()
    controller.server.running = True
    network_command_controller.handle_network_command(
        controller, lambda text: text, "match", ["match", "P1"]
    )
    assert any("Usage: match <player1_id> <player2_id>" in msg for msg in controller.cli.messages)


def test_match_success_notifies_controller():
    controller = _controller()
    controller.server.running = True

    network_command_controller.handle_network_command(
        controller, lambda text: text, "match", ["match", "P1", "P2"]
    )

    assert "notify:MATCH P1 P2" in controller.cli.messages


def test_accept_decline_cancel_cover_client_and_server_paths():
    controller = _controller()
    controller.client.connected = True

    network_command_controller.handle_network_command(
        controller, lambda text: text, "accept", ["accept"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "decline", ["decline"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "cancel", ["cancel"]
    )
    assert "send:ACCEPT" in controller.cli.messages
    assert "send:DECLINE" in controller.cli.messages
    assert "send:CANCEL" in controller.cli.messages

    controller = _controller()
    controller.server.running = True
    network_command_controller.handle_network_command(
        controller, lambda text: text, "accept", ["accept"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "decline", ["decline"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "cancel", ["cancel"]
    )
    assert "notify:RESP P1 True" in controller.cli.messages
    assert "notify:RESP P1 False" in controller.cli.messages
    assert "notify:CANCEL P1" in controller.cli.messages


def test_accept_decline_cancel_without_connection_show_error():
    controller = _controller()

    for cmd in ("accept", "decline", "cancel"):
        network_command_controller.handle_network_command(
            controller, lambda text: text, cmd, [cmd]
        )

    assert controller.cli.messages.count("Not connected to a server.") == 3


def test_join_handles_default_success_and_error():
    controller = _controller()

    network_command_controller.handle_network_command(
        controller, lambda text: text, "join", ["join"]
    )
    assert any("Connected to localhost:12345. Mode: CLIENT" in msg for msg in controller.cli.messages)

    controller = _controller()
    joined = []
    controller.client.join = lambda addr, port: joined.append((addr, port)) or "join-error"
    network_command_controller.handle_network_command(
        controller, lambda text: text, "join", ["join", "10.0.0.5:7777"]
    )
    assert joined == [("10.0.0.5", 7777)]
    assert "join-error" in controller.cli.messages


def test_ping_and_status_display_network_state():
    controller = _controller()
    controller.server.running = True
    controller.server.inbox = ["a", "b"]
    controller.server.client_socket = object()
    controller.client.connected = True
    controller.client.inbox = ["x"]
    controller.client.receiver_thread = SimpleNamespace(is_alive=lambda: True)

    network_command_controller.handle_network_command(
        controller, lambda text: text, "ping", ["ping"]
    )
    network_command_controller.handle_network_command(
        controller, lambda text: text, "status", ["status"]
    )

    assert "pong" in controller.cli.messages
    assert any("Server Running: True" in msg for msg in controller.cli.messages)
    assert any("Receiver Thread: Alive" in msg for msg in controller.cli.messages)
