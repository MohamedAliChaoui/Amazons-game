from amazons.controller.engine.game_controller import GameController
from amazons.controller.network.network_client import NetworkClient
from amazons.controller.network.network_client import NetworkDiscovery
from amazons.controller.network.network_server import NetworkServer
from amazons.model.board.move import Move
from amazons.model.players.player import NetworkPlayer


def make_move(start, end, arrow, size):
    return Move(
        Move.from_algebraic(start, size),
        Move.from_algebraic(end, size),
        Move.from_algebraic(arrow, size),
    )


def test_get_history_lines_empty():
    gc = GameController(size=4)

    assert gc.get_history_lines() == ["No moves played yet."]


def test_get_history_lines_groups_moves_by_turn():
    gc = GameController(size=4)
    gc.history = [
        (make_move("a1", "a2", "a1", 4), "W"),
        (make_move("d4", "d3", "d4", 4), "B"),
        (make_move("b1", "b2", "b1", 4), "W"),
    ]

    assert gc.get_history_lines() == [
        "1. W a1-a2/a1; B d4-d3/d4;",
        "2. W b1-b2/b1;",
    ]


def test_get_configuration_lines_reflect_runtime_settings():
    gc = GameController(
        size=8,
        time_limit_min=15,
        ai_mode="iterative",
        ai_time=7.5,
        ai_depth=4,
        ai_evaluator="mobility",
    )

    assert gc.get_configuration_lines() == [
        "Board size: 8",
        "AI mode: iterative",
        "AI time limit: 7.5s",
        "AI minimax depth: 4",
        "AI evaluator: mobility",
        "Player time limit: 15.0 min",
    ]


def test_resolve_opponent_type_accepts_shell_argument():
    gc = GameController()

    assert gc.resolve_opponent_type(["new", "aiai"]) == "aiai"


def test_resolve_opponent_type_accepts_network():
    gc = GameController()

    assert gc.resolve_opponent_type(["new", "network"]) == "network"


def test_get_local_server_addresses_filters_loopback(monkeypatch):
    gc = GameController()

    class DummySocket:
        def connect(self, _addr):
            return None

        def getsockname(self):
            return ("192.168.1.50", 50000)

        def close(self):
            return None

    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.socket.socket",
        lambda *args, **kwargs: DummySocket(),
    )
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.socket.gethostname",
        lambda: "amazons-host",
    )
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.socket.gethostbyname_ex",
        lambda _hostname: (
            "amazons-host",
            [],
            ["127.0.0.1", "192.168.1.50", "10.0.0.7"],
        ),
    )

    assert gc.get_local_server_addresses() == ["192.168.1.50", "10.0.0.7"]


def test_create_players_network_waits_for_remote_name(monkeypatch):
    gc = GameController(size=4)
    messages = []

    monkeypatch.setattr(gc.cli, "input_cli", lambda _msg: "Amine")
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc.server, "send", lambda _msg: True)
    gc.server.inbox = ["NAME Yassine"]

    assert gc.create_players("network") is True
    assert isinstance(gc.players[1], NetworkPlayer)
    assert gc.players[1].nom == "Yassine"


def test_create_players_network_fails_without_remote_name(monkeypatch):
    gc = GameController(size=4)
    messages = []
    fake_times = iter([0, 31])

    monkeypatch.setattr(gc.cli, "input_cli", lambda _msg: "Amine")
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc.server, "send", lambda _msg: True)
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.time",
        lambda: next(fake_times),
    )
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.sleep",
        lambda _seconds: None,
    )

    assert gc.create_players("network") is False
    assert any("did not send a name in time" in msg for msg in messages)


def test_close_network_session_stops_local_connections(monkeypatch):
    gc = GameController(size=4)
    actions = []

    gc.client.connected = True
    gc.client.running = True
    gc.server.running = True

    monkeypatch.setattr(
        gc.client, "quit", lambda: actions.append("client.quit") or "ok"
    )
    monkeypatch.setattr(
        gc.client, "disconnect", lambda: actions.append("client.disconnect")
    )
    monkeypatch.setattr(
        gc.server,
        "stop",
        lambda notify_client=True: actions.append(
            f"server.stop:{notify_client}"
        ) or setattr(gc.server, "running", False),
    )

    gc.close_network_session(notify_remote=True)

    assert actions == ["server.stop:True", "client.quit"]
    assert gc.server.running is False
    assert gc.is_start_party is False


# ---------------------------------------------------------------------------
# handle_set_command — syntax "set PARAM=VALUE" (spec F15) and "set P V"
# ---------------------------------------------------------------------------

def test_set_command_equals_syntax_ai_mode(capsys):
    """set ai-mode=mcts  (spec-compliant = syntax)."""
    gc = GameController()
    gc.handle_set_command(["set", "ai-mode=mcts"])
    assert gc.ai_mode == "mcts"


def test_set_command_equals_syntax_ai_time(capsys):
    """set ai-time=3.0  (spec-compliant = syntax)."""
    gc = GameController()
    gc.handle_set_command(["set", "ai-time=3.0"])
    assert gc.ai_time == 3.0


def test_set_command_equals_syntax_ai_depth(capsys):
    """set ai-depth=5  (spec-compliant = syntax)."""
    gc = GameController()
    gc.handle_set_command(["set", "ai-depth=5"])
    assert gc.ai_depth == 5


def test_set_command_equals_syntax_ai_evaluator(capsys):
    """set ai-evaluator=territory  (spec-compliant = syntax)."""
    gc = GameController()
    gc.handle_set_command(["set", "ai-evaluator=territory"])
    assert gc.ai_evaluator == "territory"


def test_set_command_space_syntax_still_works():
    """set ai-mode minimax  (backward-compatible space syntax)."""
    gc = GameController(ai_mode="mcts")
    gc.handle_set_command(["set", "ai-mode", "minimax"])
    assert gc.ai_mode == "minimax"


def test_set_command_invalid_ai_mode_prints_error():
    messages = []
    gc = GameController()
    gc.cli.error = lambda text: messages.append(text)
    gc.handle_set_command(["set", "ai-mode=badmode"])
    assert any("Invalid" in m for m in messages)
    assert gc.ai_mode != "badmode"


def test_set_command_unknown_param_prints_error():
    messages = []
    gc = GameController()
    gc.cli.msg = lambda text: messages.append(text)
    gc.handle_set_command(["set", "unknown=42"])
    assert any("Unknown parameter" in m or "unknown" in m.lower() for m in messages)


def test_set_command_bad_syntax_prints_usage():
    messages = []
    gc = GameController()
    gc.cli.msg = lambda text: messages.append(text)
    gc.handle_set_command(["set"])
    assert any("Usage" in m or "usage" in m.lower() for m in messages)


def test_network_server_defaults_match_f38():
    server = NetworkServer()

    assert server.broadcast_interval == 10.0
    assert server.inactivity_timeout == 60.0


def test_network_discovery_uses_30_second_timeout(monkeypatch):
    discovery = NetworkDiscovery()
    discovery.servers = {
        "fresh": {"name": "A", "last_seen": 91},
        "stale": {"name": "B", "last_seen": 50},
    }

    monkeypatch.setattr(
        "amazons.controller.network.network_client.time.time", lambda: 120
    )

    servers = discovery.get_server_list()

    assert [server["name"] for server in servers] == ["A"]


def test_network_server_stop_notifies_connected_client():
    server = NetworkServer()
    sent_payloads = []

    class DummySocket:
        def close(self):
            sent_payloads.append("closed")

        def sendall(self, payload):
            sent_payloads.append(payload)

    server.client_socket = DummySocket()
    server.running = True

    server.stop(notify_client=True)

    assert sent_payloads[0] == b"SERVER_STOP\n"
    assert "closed" in sent_payloads


def test_network_server_tracks_connected_players():
    server = NetworkServer()

    class DummySocket:
        def close(self):
            return None

    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    server._update_player(player_id, name="Amine", status="ingame")

    assert player_id == "P1"
    assert server.get_status()["connected_clients"] == 1
    assert server.get_status()["parties_in_progress"] == 1
    assert server.get_player("P1")["name"] == "Amine"
    assert server.get_players()[0]["status"] == "ingame"


def test_network_server_records_scoreboard_entries():
    server = NetworkServer()

    class DummySocket:
        def close(self):
            return None

    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    server._update_player(player_id, name="Remote", status="idle")
    server.begin_hosted_game("Host", player_id=player_id)
    server.record_completed_game("win", "loss", player_id=player_id)

    scoreboard = server.get_scoreboard()

    assert scoreboard == [
        {"name": "Host", "wins": 1, "losses": 0, "played": 1},
        {"name": "Remote", "wins": 0, "losses": 1, "played": 1},
    ]
    assert server.host_player["status"] == "idle"
    assert server.get_player(player_id)["status"] == "idle"


def test_network_server_invitation_flow():
    server = NetworkServer()
    notifications = []

    class DummySocket:
        def close(self):
            return None

        def sendall(self, payload):
            notifications.append(payload.decode("ascii").strip())

    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    assert server.receive() == "PLAYER_CONNECTED P1 Player1"
    server._update_player(player_id, name="Remote", status="idle")
    server.set_host_player("Host", status="idle")

    sent = server.request_invitation(server.host_player_id, player_id)

    assert sent == "INVITE_SENT P1 Remote"
    assert notifications[-1] == "INVITE_FROM HOST Host"
    assert server.get_player(player_id)["status"] == "waitgame"

    accepted = server.respond_to_invitation(player_id, accepted=True)

    assert accepted == "INVITE_ACCEPTED HOST Host"
    assert server.host_player["status"] == "ingame"
    assert server.get_player(player_id)["status"] == "ingame"
    assert server.receive() == "INVITE_ACCEPTED P1 Remote"
    assert server.receive() == "HOST_START_GAME P1"


def test_network_server_starts_client_match_between_two_clients():
    server = NetworkServer()

    class DummySocket:
        def __init__(self):
            self.sent = []

        def close(self):
            return None

        def sendall(self, payload):
            self.sent.append(payload.decode("ascii").strip())

    white_socket = DummySocket()
    black_socket = DummySocket()
    white_id = server._register_player(white_socket, ("127.0.0.1", 6001))
    black_id = server._register_player(black_socket, ("127.0.0.1", 6002))
    server._update_player(white_id, name="ClientOne", status="idle")
    server._update_player(black_id, name="ClientTwo", status="idle")

    result = server.start_client_match(white_id, black_id, size=6, time_limit=90.0)

    assert result.startswith("CLIENT_MATCH_STARTED")
    assert white_socket.sent == [
        "NAME ClientTwo",
        "START 6 BLACK 90.000",
    ]
    assert black_socket.sent == [
        "NAME ClientOne",
        "START 6 WHITE 90.000",
    ]
    assert server.get_player(white_id)["status"] == "ingame"
    assert server.get_player(black_id)["status"] == "ingame"


def test_network_server_relays_client_match_moves_and_records_scores():
    server = NetworkServer()

    class DummySocket:
        def __init__(self):
            self.sent = []

        def close(self):
            return None

        def sendall(self, payload):
            self.sent.append(payload.decode("ascii").strip())

    white_socket = DummySocket()
    black_socket = DummySocket()
    white_id = server._register_player(white_socket, ("127.0.0.1", 6101))
    black_id = server._register_player(black_socket, ("127.0.0.1", 6102))
    server._update_player(white_id, name="ClientOne", status="idle")
    server._update_player(black_id, name="ClientTwo", status="idle")
    server.start_client_match(white_id, black_id, size=4, time_limit=60.0)
    white_socket.sent.clear()
    black_socket.sent.clear()

    server._handle_client_game_message(white_id, "MOVE a4-a3/a2")

    assert black_socket.sent == ["MOVE Wa4-a3/a2"]

    server._handle_client_game_message(black_id, "MOVE d1-d2/d3")

    assert white_socket.sent == ["MOVE Bd1-d2/d3"]

    session_id = server._get_session_id_for_player(white_id)
    server._finish_client_session(
        session_id,
        winner_color="B",
        reason="GAMEOVER WINNER=B ClientTwo wins.",
    )

    assert white_socket.sent[-1] == "GAMEOVER WINNER=B ClientTwo wins."
    assert black_socket.sent[-1] == "GAMEOVER WINNER=B ClientTwo wins."


def test_network_server_register_player_emits_connected_message():
    server = NetworkServer()
    seen = []
    server.on_message_received = lambda message: seen.append(message)

    class DummySocket:
        def close(self):
            return None

        def sendall(self, _payload):
            return None

    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))

    assert player_id == "P1"
    assert server.receive() == "PLAYER_CONNECTED P1 Player1"
    assert seen == ["PLAYER_CONNECTED P1 Player1"]


def test_network_server_notify_message_received_supports_zero_arg_callback():
    server = NetworkServer()
    seen = []
    server.on_message_received = lambda: seen.append("called")

    server._notify_message_received("ignored")

    assert seen == ["called"]


def test_network_server_notify_message_received_swallows_callback_errors():
    server = NetworkServer()
    server.on_message_received = lambda _message: (_ for _ in ()).throw(RuntimeError("boom"))

    server._notify_message_received("hello")


def test_network_server_get_status_counts_host_and_standalone_ingame():
    server = NetworkServer()
    server.running = True
    server.tcp_port = 5555
    server.host_player["status"] = "ingame"
    server.connected_players = {
        "P1": {"id": "P1", "status": "ingame"},
        "P2": {"id": "P2", "status": "idle"},
    }

    status = server.get_status()

    assert status["running"] is True
    assert status["port"] == 5555
    assert status["connected_clients"] == 2
    assert status["parties_in_progress"] == 2


def test_network_server_record_completed_game_uses_active_player_when_needed():
    server = NetworkServer()
    server.host_player["name"] = "Host"
    server.active_player_id = "P1"
    server.connected_players = {
        "P1": {"id": "P1", "name": "Remote", "status": "ingame", "address": ("127.0.0.1", 1)}
    }

    server.record_completed_game("win", "loss")

    assert server.get_scoreboard() == [
        {"name": "Host", "wins": 1, "losses": 0, "played": 1},
        {"name": "Remote", "wins": 0, "losses": 1, "played": 1},
    ]


def test_network_server_accept_selects_active_client_socket():
    server = NetworkServer()

    class DummySocket:
        def __init__(self, name):
            self.name = name
            self.sent = []

        def close(self):
            return None

        def sendall(self, payload):
            self.sent.append(payload.decode("ascii").strip())

    player_one_socket = DummySocket("P1")
    player_two_socket = DummySocket("P2")

    player_one_id = server._register_player(
        player_one_socket, ("127.0.0.1", 5555)
    )
    player_two_id = server._register_player(
        player_two_socket, ("127.0.0.1", 5556)
    )
    server._update_player(player_one_id, name="First", status="idle")
    server._update_player(player_two_id, name="Second", status="idle")
    server.set_host_player("Host", status="idle")

    server.request_invitation(server.host_player_id, player_two_id)
    server.respond_to_invitation(player_two_id, accepted=True)

    server.send("MOVE We2-e4/e6")

    assert server.active_player_id == player_two_id
    assert player_one_socket.sent == []
    assert player_two_socket.sent[-1] == "MOVE We2-e4/e6"


def test_network_server_cancel_invitation_resets_status():
    server = NetworkServer()

    class DummySocket:
        def close(self):
            return None

        def sendall(self, _payload):
            return None

    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    server._update_player(player_id, name="Remote", status="idle")
    server.set_host_player("Host", status="idle")
    server.request_invitation(server.host_player_id, player_id)

    result = server.cancel_invitation(server.host_player_id)

    assert result == "INVITE_CANCELLED P1 Remote"
    assert server.host_player["status"] == "idle"
    assert server.get_player(player_id)["status"] == "idle"


def test_network_server_disconnect_clears_invitation_and_records_host_win():
    server = NetworkServer()

    class DummySocket:
        def __init__(self, label):
            self.label = label

        def close(self):
            return None

        def sendall(self, payload):
            return None

    invited_socket = DummySocket("invited")
    other_socket = DummySocket("other")

    invited_id = server._register_player(
        invited_socket, ("127.0.0.1", 5555)
    )
    other_id = server._register_player(other_socket, ("127.0.0.1", 5556))
    assert server.receive() == "PLAYER_CONNECTED P1 Player1"
    assert server.receive() == "PLAYER_CONNECTED P2 Player2"
    server._update_player(invited_id, name="Invited", status="idle")
    server._update_player(other_id, name="Other", status="idle")
    server.set_host_player("Host", status="idle")

    server.request_invitation(server.host_player_id, other_id)
    server._unregister_player(other_id)

    assert server.host_player["status"] == "idle"
    assert server.get_pending_invitations() == []
    assert server.receive() == "INVITE_CANCELLED P2 Other"

    server.begin_hosted_game("Host", player_id=invited_id)
    server._unregister_player(invited_id)

    scoreboard = server.get_scoreboard()

    assert scoreboard == [
        {"name": "Host", "wins": 1, "losses": 0, "played": 1},
        {"name": "Invited", "wins": 0, "losses": 1, "played": 1},
    ]
    assert server.host_player["status"] == "idle"


def test_network_server_inactivity_timeout_closes_idle_client(monkeypatch):
    server = NetworkServer()
    server.running = True
    notifications = []

    class DummyClient:
        def __init__(self):
            self.closed = False

        def settimeout(self, _timeout):
            return None

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        server,
        "_notify_client",
        lambda msg: notifications.append(msg) or True,
    )
    monkeypatch.setattr(
        "amazons.controller.network.network_server.time.monotonic",
        iter([0.0, 61.0]).__next__,
    )

    class TimeoutClient(DummyClient):
        def recv(self, _size):
            import socket

            raise socket.timeout()

    timeout_client = TimeoutClient()
    server.client_socket = timeout_client

    server._handle_client(timeout_client)

    assert notifications == ["TIMEOUT"]
    assert timeout_client.closed is True


def test_network_server_ignores_keepalive_messages():
    server = NetworkServer()
    server.running = True

    class KeepAliveClient:
        def __init__(self):
            self.closed = False
            self.payloads = [b"KEEPALIVE\n", b""]

        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            return self.payloads.pop(0)

        def close(self):
            self.closed = True

        def sendall(self, _payload):
            raise AssertionError("KEEPALIVE should not trigger a response")

    keepalive_client = KeepAliveClient()
    server.client_socket = keepalive_client

    server._handle_client(keepalive_client)

    assert server.receive() is None
    assert keepalive_client.closed is True


def test_network_client_keepalive_loop_sends_heartbeat(monkeypatch):
    client = NetworkClient()
    sent = []
    client.connected = True
    client.running = True
    client.keepalive_interval = 0.01

    monkeypatch.setattr(client, "send", lambda message: sent.append(message) or True)

    def stop_after_first_sleep(_delay):
        client.running = False

    monkeypatch.setattr("amazons.controller.network.network_client.time.sleep", stop_after_first_sleep)

    client._keepalive_loop()

    assert sent == ["KEEPALIVE"]


def test_quit_disconnects_network_then_allows_regular_exit(monkeypatch):
    gc = GameController(size=4)
    messages = []
    commands = iter(["quit", "quit"])

    gc.client.connected = True
    monkeypatch.setattr(gc.cli, "welcome", lambda _size: None)
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="": next(commands))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    monkeypatch.setattr(
        gc,
        "close_network_session",
        lambda notify_remote=True: setattr(gc.client, "connected", False),
    )
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert "Network session closed." in messages
    assert "Bye!" in messages


def test_server_status_command_displays_server_summary(monkeypatch):
    gc = GameController(size=4)
    messages = []

    gc.server.get_status = lambda: {
        "port": 12345,
        "connected_clients": 2,
        "parties_in_progress": 1,
        "active_player_id": "P1",
    }
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc.cli, "welcome", lambda _size: None)
    monkeypatch.setattr(
        gc,
        "_get_input_or_network",
        lambda prompt="": "server status" if not messages else "quit",
    )
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert any("Connected clients: 2" in msg for msg in messages)
    assert any("Parties in progress: 1" in msg for msg in messages)


def test_players_command_lists_connected_players(monkeypatch):
    gc = GameController(size=4)
    messages = []
    commands = iter(["players", "quit"])

    gc.server.get_players = lambda: [
        {
            "id": "P1",
            "name": "Amine",
            "status": "idle",
            "address": ("192.168.1.10", 4000),
        }
    ]
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc.cli, "welcome", lambda _size: None)
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="": next(commands))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert any("P1: Amine | idle | 192.168.1.10:4000" in msg for msg in messages)


def test_scoreboard_command_lists_scores(monkeypatch):
    gc = GameController(size=4)
    messages = []
    commands = iter(["scoreboard", "quit"])

    gc.server.get_scoreboard = lambda: [
        {"name": "Host", "wins": 2, "losses": 1, "played": 3}
    ]
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc.cli, "welcome", lambda _size: None)
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="": next(commands))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert any("Host: 2 win(s), 1 loss(es), 3 game(s)" in msg for msg in messages)


def test_new_player_id_sends_host_invitation(monkeypatch):
    gc = GameController(size=4)
    messages = []
    prompts = iter(["Ayoub"])
    commands = iter(["new P1", "quit"])

    gc.server.running = True
    monkeypatch.setattr(gc.cli, "msg", lambda text: messages.append(text))
    monkeypatch.setattr(gc.cli, "welcome", lambda _size: None)
    monkeypatch.setattr(gc.cli, "input_cli", lambda prompt="": next(prompts))
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="": next(commands))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)
    monkeypatch.setattr(
        gc.server,
        "request_invitation",
        lambda inviter_id, invitee_id: f"INVITE_SENT {invitee_id} Remote",
    )

    gc.start()

    assert gc.server.host_player["name"] == "Ayoub"
    assert any("Invitation sent to P1 (Remote)." in msg for msg in messages)
