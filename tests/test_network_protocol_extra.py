import socket
import importlib
from unittest.mock import MagicMock

from amazons.controller.network import network_client as network_client_module
from amazons.controller.network.network_client import (
    NetworkClient,
    NetworkDiscovery,
)
from amazons.controller.network.network_server import NetworkServer
from amazons.model.board.board import Board
from amazons.model.board.move import Move


class DummySocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    def close(self):
        self.closed = True

    def sendall(self, payload):
        self.sent.append(payload.decode("ascii").strip())


def _make_session(server, size=6):
    board = Board(size)
    session_id = "S1"
    session = {
        "id": session_id,
        "size": size,
        "time_limit": 1800.0,
        "board": board,
        "history": [],
        "players": {"W": "P1", "B": "P2"},
        "player_colors": {"P1": "W", "P2": "B"},
        "names": {"W": "White", "B": "Black"},
        "pending_undo_requester_id": None,
        "pending_undo_requester_color": None,
        "pending_undo_requested_at": None,
    }
    server.active_sessions[session_id] = session
    server.player_sessions["P1"] = session_id
    server.player_sessions["P2"] = session_id
    return session


def test_network_server_message_requires_active_game():
    server = NetworkServer()

    assert server._message_requires_active_game("MOVE a4-a3/a2") is True
    assert server._message_requires_active_game("CLOCK W 12") is True
    assert server._message_requires_active_game("UNDO_REQ W") is True
    assert server._message_requires_active_game("NAME Alice") is False


def test_network_server_start_rejects_duplicate_launch():
    server = NetworkServer()
    server.running = True

    assert server.start() == "Server is already running."


def test_network_server_start_spawns_listener_and_broadcaster(monkeypatch):
    server = NetworkServer()
    started = []

    class FakeServerSocket:
        def setsockopt(self, *args):
            return None

        def bind(self, addr):
            self.bound = addr

        def listen(self, backlog):
            self.backlog = backlog

        def settimeout(self, timeout):
            self.timeout = timeout

    class DummyThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append(self.target.__name__)

    monkeypatch.setattr(
        "amazons.controller.network.network_server.socket.socket",
        lambda *_args, **_kwargs: FakeServerSocket(),
    )
    monkeypatch.setattr(
        "amazons.controller.network.network_server.threading.Thread",
        DummyThread,
    )

    assert server.start(port=23456) is None
    assert server.running is True
    assert started == ["_tcp_listener", "_udp_broadcaster"]
    assert server.tcp_port == 23456


def test_network_server_start_reports_socket_error(monkeypatch):
    server = NetworkServer()

    class FailingServerSocket:
        def setsockopt(self, *args):
            return None

        def bind(self, addr):
            raise OSError("busy")

    monkeypatch.setattr(
        "amazons.controller.network.network_server.socket.socket",
        lambda *_args, **_kwargs: FailingServerSocket(),
    )

    assert "Error starting TCP server" in server.start(port=34567)


def test_network_server_stop_closes_threads_and_server_socket():
    server = NetworkServer()
    joined = []

    class DummyThread:
        def join(self, timeout):
            joined.append(timeout)

    class ClosableSocket:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    server.running = True
    server.server_socket = ClosableSocket()
    server.client_socket = ClosableSocket()
    server.tcp_thread = DummyThread()
    server.udp_thread = DummyThread()

    server.stop(notify_client=False)

    assert server.server_socket is None
    assert server.client_socket is None
    assert joined == [2.0, 2.0]


def test_network_server_udp_broadcaster_sends_one_broadcast(monkeypatch):
    server = NetworkServer()
    server.running = True
    payloads = []

    class FakeUdpSocket:
        def setsockopt(self, *args):
            return None

        def sendto(self, payload, addr):
            payloads.append((payload, addr))
            server.running = False

        def close(self):
            payloads.append(("closed", None))

    monkeypatch.setattr(
        "amazons.controller.network.network_server.socket.socket",
        lambda *_args, **_kwargs: FakeUdpSocket(),
    )

    server._udp_broadcaster()

    assert payloads[0][0] == f"{server.server_name}:{server.tcp_port}".encode("utf-8")
    assert payloads[0][1] == ("<broadcast>", server.udp_port)
    assert payloads[-1] == ("closed", None)


def test_network_server_tcp_listener_registers_one_client(monkeypatch):
    server = NetworkServer()
    server.running = True
    accepted = []
    started = []

    class FakeClient:
        pass

    class FakeListenerSocket:
        def __init__(self):
            self.calls = 0

        def accept(self):
            self.calls += 1
            if self.calls == 1:
                server.running = False
                return FakeClient(), ("127.0.0.1", 5000)
            raise OSError("closed")

    class DummyThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target.__name__, self.args[1]))

    server.server_socket = FakeListenerSocket()
    monkeypatch.setattr(server, "_register_player", lambda client, addr: accepted.append(addr) or "P1")
    monkeypatch.setattr(
        "amazons.controller.network.network_server.threading.Thread",
        DummyThread,
    )

    server._tcp_listener()

    assert accepted == [("127.0.0.1", 5000)]
    assert started == [("_handle_client", "P1")]


def test_network_server_handle_client_processes_ping_name_and_quit(monkeypatch):
    server = NetworkServer()
    server.running = True
    updated = []
    seen = []
    closed = []

    class FakeClient:
        def __init__(self):
            self.payloads = []
            self.recv_calls = 0

        def settimeout(self, timeout):
            return None

        def recv(self, _size):
            self.recv_calls += 1
            if self.recv_calls == 1:
                return b"PING\nNAME Alice\nQUIT\n"
            return b""

        def sendall(self, payload):
            self.payloads.append(payload.decode("ascii").strip())

        def close(self):
            closed.append(True)

    client = FakeClient()
    monkeypatch.setattr(server, "_update_player", lambda player_id, **updates: updated.append((player_id, updates)) or True)
    monkeypatch.setattr(server, "_notify_message_received", lambda message: seen.append(message))
    monkeypatch.setattr(server, "_close_client", lambda client=None, player_id=None: closed.append(player_id))

    server._handle_client(client, player_id="P1")

    assert client.payloads == ["PONG", "BYE"]
    assert updated == [("P1", {"name": "Alice"})]
    assert server.receive() == "NAME Alice"
    assert seen == ["NAME Alice"]
    assert closed == ["P1"]


def test_network_server_handle_client_dispatches_invitation_commands(monkeypatch):
    server = NetworkServer()
    server.running = True
    replies = []
    called = []

    class FakeClient:
        def __init__(self):
            self.recv_calls = 0

        def settimeout(self, timeout):
            return None

        def recv(self, _size):
            self.recv_calls += 1
            if self.recv_calls == 1:
                return b"INVITE P2\nACCEPT\nDECLINE\nCANCEL\n"
            return b""

    monkeypatch.setattr(server, "request_invitation", lambda player_id, target_id: called.append(("invite", player_id, target_id)) or "INVITE_SENT")
    monkeypatch.setattr(server, "respond_to_invitation", lambda player_id, accepted: called.append(("reply", player_id, accepted)) or "INVITE_REPLY")
    monkeypatch.setattr(server, "cancel_invitation", lambda player_id: called.append(("cancel", player_id)) or "INVITE_CANCELLED")
    monkeypatch.setattr(server, "send", lambda message, player_id=None: replies.append((player_id, message)) or True)
    monkeypatch.setattr(server, "_close_client", lambda client=None, player_id=None: None)

    server._handle_client(FakeClient(), player_id="P1")

    assert called == [
        ("invite", "P1", "P2"),
        ("reply", "P1", True),
        ("reply", "P1", False),
        ("cancel", "P1"),
    ]
    assert replies == [
        ("P1", "INVITE_SENT"),
        ("P1", "INVITE_REPLY"),
        ("P1", "INVITE_REPLY"),
        ("P1", "INVITE_CANCELLED"),
    ]


def test_network_server_handle_client_times_out_specific_player(monkeypatch):
    server = NetworkServer()
    server.running = True
    notifications = []

    class TimeoutClient:
        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            raise socket.timeout()

    monkeypatch.setattr(
        "amazons.controller.network.network_server.time.monotonic",
        iter([0.0, 61.0]).__next__,
    )
    monkeypatch.setattr(
        server,
        "_notify_client",
        lambda msg, player_id=None: notifications.append((player_id, msg)) or True,
    )
    monkeypatch.setattr(server, "_close_client", lambda client=None, player_id=None: None)

    server._handle_client(TimeoutClient(), player_id="P1")

    assert notifications == [("P1", "TIMEOUT")]


def test_network_server_game_message_errors_without_active_session():
    server = NetworkServer()
    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    assert server._handle_client_game_message(player_id, "MOVE a4-a3/a2") is True
    assert errors == [
        (player_id, "ERROR No active game is associated with this player.")
    ]


def test_network_server_request_invitation_rejects_invalid_states():
    server = NetworkServer()
    server.set_host_player("Host", status="idle")
    player_one = server._register_player(DummySocket(), ("127.0.0.1", 5001))
    player_two = server._register_player(DummySocket(), ("127.0.0.1", 5002))
    server._update_player(player_one, name="Alice", status="idle")
    server._update_player(player_two, name="Bob", status="idle")

    assert server.request_invitation("P999", player_two) == "ERROR Unknown inviter."
    assert server.request_invitation(player_one, "P999") == "ERROR Unknown player ID."
    assert server.request_invitation(player_one, player_one) == "ERROR You cannot invite yourself."

    server._update_player(player_one, status="ingame")
    assert server.request_invitation(player_one, player_two) == "ERROR You are not available."
    server._update_player(player_one, status="idle")

    server._update_player(player_two, status="ingame")
    assert server.request_invitation(player_one, player_two) == "ERROR Target player is not available."


def test_network_server_request_invitation_rejects_pending_conflicts():
    server = NetworkServer()
    player_one = server._register_player(DummySocket(), ("127.0.0.1", 5001))
    player_two = server._register_player(DummySocket(), ("127.0.0.1", 5002))
    player_three = server._register_player(DummySocket(), ("127.0.0.1", 5003))
    server._update_player(player_one, name="Alice", status="idle")
    server._update_player(player_two, name="Bob", status="idle")
    server._update_player(player_three, name="Cara", status="idle")

    assert server.request_invitation(player_one, player_two) == "INVITE_SENT P2 Bob"
    assert (
        server.request_invitation(player_one, player_three)
        == "ERROR You are not available."
    )
    assert (
        server.request_invitation(player_three, player_two)
        == "ERROR Target player is not available."
    )


def test_network_server_game_message_returns_false_for_hosted_remote_player():
    server = NetworkServer()
    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    server.host_player["status"] = "ingame"
    server.active_player_id = player_id

    assert server._handle_client_game_message(player_id, "MOVE a4-a3/a2") is False


def test_network_server_game_message_allows_clock_and_gameover_without_session():
    server = NetworkServer()
    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))

    assert server._handle_client_game_message(player_id, "CLOCK W 12.0") is True
    assert server._handle_client_game_message(player_id, "GAMEOVER done") is True


def test_network_server_parse_and_format_network_move_round_trip():
    server = NetworkServer()
    color, move = server._parse_network_move("Wa4-a3/a2", 4)

    assert color == "W"
    assert server._format_network_move(move, color, 4) == "MOVE Wa4-a3/a2"


def test_network_server_get_player_returns_none_for_unknown_id():
    server = NetworkServer()

    assert server.get_player("P9") is None


def test_network_server_set_active_player_rejects_unknown_id():
    server = NetworkServer()

    assert server.set_active_player("P9") is False


def test_network_server_get_session_for_unknown_player_returns_none():
    server = NetworkServer()

    assert server._get_session_for_player("P9") is None


def test_network_server_get_session_opponent_returns_none_without_other_player():
    server = NetworkServer()
    session = {"player_colors": {"P1": "W"}}

    assert server._get_session_opponent(session, "P1") is None


def test_network_server_session_can_undo_returns_false_without_color():
    server = NetworkServer()
    session = {"history": []}

    assert server._session_can_undo(session, "W") is False


def test_network_server_finish_client_session_returns_false_for_unknown_session():
    server = NetworkServer()

    assert server._finish_client_session("S9") is False


def test_network_server_respond_to_invitation_decline_notifies_inviter():
    server = NetworkServer()
    notified = []
    player_id = server._register_player(DummySocket(), ("127.0.0.1", 5555))
    server._update_player(player_id, name="Remote", status="idle")
    server.set_host_player("Host", status="idle")
    server.request_invitation(server.host_player_id, player_id)
    server._notify_actor = lambda actor_id, message: notified.append((actor_id, message)) or True

    result = server.respond_to_invitation(player_id, accepted=False)

    assert result == "INVITE_DECLINED HOST Host"
    assert notified == [("HOST", f"INVITE_DECLINED {player_id} Remote")]


def test_network_server_respond_to_invitation_rejects_missing_request():
    server = NetworkServer()

    assert server.respond_to_invitation("P1", accepted=True) == "ERROR No pending invitation."


def test_network_server_respond_to_invitation_rejects_stale_players():
    server = NetworkServer()
    server.pending_invitations = {
        "P2": {
            "from_id": "P1",
            "from_name": "Alice",
            "to_id": "P2",
            "to_name": "Bob",
            "created_at": 10.0,
        }
    }
    import time
    now = time.time()
    server.pending_invitations["P2"]["created_at"] = now

    assert (
        server.respond_to_invitation("P2", accepted=True)
        == "ERROR Invitation is no longer valid."
    )


def test_network_server_cancel_invitation_requires_pending_request():
    server = NetworkServer()

    assert (
        server.cancel_invitation("P1")
        == "ERROR No pending invitation to cancel."
    )


def test_network_server_start_client_match_rejects_invalid_inputs():
    server = NetworkServer()
    player_one = server._register_player(DummySocket(), ("127.0.0.1", 5001))
    player_two = server._register_player(DummySocket(), ("127.0.0.1", 5002))
    server._update_player(player_one, name="Alice", status="idle")
    server._update_player(player_two, name="Bob", status="idle")

    assert server.start_client_match(player_one, player_one) == "ERROR Select two different players."
    assert server.start_client_match(player_one, "P999") == "ERROR Unknown player ID."

    server._update_player(player_two, status="ingame")
    assert server.start_client_match(player_one, player_two) == "ERROR Both players must be idle."


def test_network_server_start_client_match_rejects_existing_session():
    server = NetworkServer()
    player_one = server._register_player(DummySocket(), ("127.0.0.1", 5001))
    player_two = server._register_player(DummySocket(), ("127.0.0.1", 5002))
    server._update_player(player_one, name="Alice", status="idle")
    server._update_player(player_two, name="Bob", status="idle")
    server.player_sessions[player_one] = "S99"

    assert (
        server.start_client_match(player_one, player_two)
        == "ERROR One selected player is already in a game."
    )


def test_network_server_start_client_match_reports_notification_failure():
    server = NetworkServer()
    player_one = server._register_player(DummySocket(), ("127.0.0.1", 5001))
    player_two = server._register_player(DummySocket(), ("127.0.0.1", 5002))
    server._update_player(player_one, name="Alice", status="idle")
    server._update_player(player_two, name="Bob", status="idle")
    finished = []
    server._notify_actor = lambda actor_id, message: actor_id != player_two
    server._finish_client_session = (
        lambda session_id, **kwargs: finished.append((session_id, kwargs)) or True
    )

    result = server.start_client_match(player_one, player_two, size=6, time_limit=60.0)

    assert result == "ERROR Failed to notify both clients."
    assert finished


def test_network_server_session_clock_rejects_wrong_color():
    server = NetworkServer()
    _make_session(server)
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    server._handle_client_session_clock("S1", "P1", "CLOCK B 12.0")

    assert errors == [("P1", "ERROR Clock color does not match this player.")]


def test_network_server_session_move_rejects_wrong_turn():
    server = NetworkServer()
    session = _make_session(server)
    first_move = Move(
        Move.from_algebraic("c6", 6),
        Move.from_algebraic("c5", 6),
        Move.from_algebraic("b5", 6),
    )
    session["board"].make_move(first_move, "W")
    session["history"].append((first_move, "W"))
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    server._handle_client_session_move("S1", "P1", "c5-c4/c3")

    assert errors == [("P1", "ERROR It is not your turn.")]


def test_network_server_session_move_rejects_invalid_notation():
    server = NetworkServer()
    _make_session(server)
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    server._handle_client_session_move("S1", "P1", "not-a-move")

    assert errors == [("P1", "ERROR Invalid move notation.")]


def test_network_server_session_move_rejects_color_mismatch():
    server = NetworkServer()
    _make_session(server)
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    server._handle_client_session_move("S1", "P1", "Ba4-a3/a2")

    assert errors == [("P1", "ERROR Move color does not match this player.")]


def test_network_server_session_move_rejects_invalid_move_geometry():
    server = NetworkServer()
    _make_session(server)
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    server._handle_client_session_move("S1", "P1", "a1-a1/a1")

    assert errors
    assert errors[0][0] == "P1"
    assert errors[0][1].startswith("ERROR ")


def test_network_server_handle_client_session_message_dispatches_protocol_branches():
    server = NetworkServer()
    called = []
    server._handle_client_session_move = lambda session_id, player_id, notation: called.append(("move", session_id, player_id, notation))
    server._handle_client_session_clock = lambda session_id, player_id, message: called.append(("clock", session_id, player_id, message))
    server._handle_client_session_undo_request = lambda session_id, player_id, message: called.append(("undo_req", session_id, player_id, message))
    server._handle_client_session_undo_reply = lambda session_id, player_id, accepted: called.append(("undo_reply", session_id, player_id, accepted))
    server._handle_client_session_gameover = lambda session_id, player_id, message: called.append(("gameover", session_id, player_id, message))
    server.send = lambda message, player_id=None: called.append(("send", player_id, message)) or True

    server._handle_client_session_message("S1", "P1", "MOVE a4-a3/a2")
    server._handle_client_session_message("S1", "P1", "CLOCK W 12.0")
    server._handle_client_session_message("S1", "P1", "UNDO_REQ W")
    server._handle_client_session_message("S1", "P1", "UNDO_OK")
    server._handle_client_session_message("S1", "P1", "UNDO_NO")
    server._handle_client_session_message("S1", "P1", "GAMEOVER done")
    server._handle_client_session_message("S1", "P1", "LOAD_STATE payload")

    assert called == [
        ("move", "S1", "P1", "a4-a3/a2"),
        ("clock", "S1", "P1", "CLOCK W 12.0"),
        ("undo_req", "S1", "P1", "UNDO_REQ W"),
        ("undo_reply", "S1", "P1", True),
        ("undo_reply", "S1", "P1", False),
        ("gameover", "S1", "P1", "GAMEOVER done"),
        ("send", "P1", "ERROR Save synchronization is only supported in host matches."),
    ]


def test_network_server_undo_reply_rejects_requester():
    server = NetworkServer()
    session = _make_session(server)
    session["pending_undo_requester_id"] = "P1"
    session["pending_undo_requester_color"] = "W"
    errors = []
    server.send = lambda message, player_id=None: errors.append((player_id, message)) or True

    server._handle_client_session_undo_reply("S1", "P1", accepted=True)

    assert errors == [("P1", "ERROR Only the opponent can answer an undo request.")]


def test_network_server_gameover_falls_back_to_reporting_player():
    server = NetworkServer()
    _make_session(server)
    finished = []
    server._finish_client_session = (
        lambda session_id, winner_color=None, reason=None, **kwargs:
        finished.append((session_id, winner_color, reason))
    )

    server._handle_client_session_gameover("S1", "P1", "GAMEOVER no winner token")

    assert finished == [("S1", "W", "GAMEOVER no winner token")]


def test_network_server_gameover_uses_explicit_winner_token():
    server = NetworkServer()
    _make_session(server)
    finished = []
    server._finish_client_session = (
        lambda session_id, winner_color=None, reason=None, **kwargs:
        finished.append((session_id, winner_color, reason))
    )

    server._handle_client_session_gameover(
        "S1",
        "P1",
        "GAMEOVER WINNER=B Black wins.",
    )

    assert finished == [("S1", "B", "GAMEOVER WINNER=B Black wins.")]


def test_network_server_notify_client_handles_missing_socket():
    server = NetworkServer()

    assert server._notify_client("PING") is False


def test_network_server_notify_client_handles_send_failure():
    server = NetworkServer()

    class FailingSocket:
        def sendall(self, payload):
            raise OSError("boom")

    server.client_socket = FailingSocket()

    assert server._notify_client("PING") is False


def test_network_server_prunes_expired_invitations(monkeypatch):
    server = NetworkServer()
    server.pending_invitations = {
        "P2": {
            "from_id": "P1",
            "from_name": "Alice",
            "to_id": "P2",
            "to_name": "Bob",
            "created_at": 0.0,
        }
    }
    notifications = []
    monkeypatch.setattr(
        "amazons.controller.network.network_server.time.time",
        lambda: server.invitation_timeout + 1.0,
    )
    server._notify_actor = lambda actor_id, message: notifications.append((actor_id, message)) or True

    server._prune_expired_invitations()

    assert server.pending_invitations == {}
    assert ("P1", "INVITE_EXPIRED P2 Bob") in notifications
    assert ("P2", "INVITE_EXPIRED P1 Alice") in notifications


def test_network_client_ping_requires_connection():
    client = NetworkClient()

    assert client.ping() == "Not connected."


def test_network_client_quit_handles_exception(monkeypatch):
    client = NetworkClient()
    client.connected = True
    monkeypatch.setattr(
        client,
        "send",
        lambda message: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert "Quit error" in client.quit()


def test_network_client_ping_reports_timeout(monkeypatch):
    client = NetworkClient()
    client.connected = True
    monkeypatch.setattr(client, "send", lambda message: True)
    monkeypatch.setattr(client, "_wait_for_response", lambda prefix, timeout=5.0: None)

    assert client.ping() == "Ping timeout (no PONG received)"


def test_network_client_receive_loop_handles_server_eof(monkeypatch):
    client = NetworkClient()
    client.running = True

    class EofSocket:
        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            return b""

    client.socket = EofSocket()
    disconnected = []
    monkeypatch.setattr(
        client,
        "disconnect",
        lambda: disconnected.append(True) or setattr(client, "running", False),
    )

    client._receive_loop()

    assert client.disconnect_reason == "Server closed the connection."
    assert disconnected == [True]


def test_network_client_receive_loop_handles_unexpected_exception(monkeypatch):
    client = NetworkClient()
    client.running = True

    class BrokenSocket:
        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            raise RuntimeError("boom")

    client.socket = BrokenSocket()
    disconnected = []
    monkeypatch.setattr(
        client,
        "disconnect",
        lambda: disconnected.append(True) or setattr(client, "running", False),
    )

    client._receive_loop()

    assert client.disconnect_reason == "Connection lost unexpectedly."
    assert disconnected == [True]


def test_network_client_send_returns_false_on_socket_error():
    client = NetworkClient()

    class FailingSocket:
        def sendall(self, payload):
            raise OSError("boom")

    client.connected = True
    client.socket = FailingSocket()

    assert client.send("PING") is False


def test_network_client_receive_returns_none_when_empty():
    client = NetworkClient()

    assert client.receive() is None


def test_network_client_disconnect_ignores_close_errors():
    client = NetworkClient()

    class FailingSocket:
        def close(self):
            raise OSError("boom")

    client.socket = FailingSocket()
    client.connected = True
    client.running = True

    client.disconnect()

    assert client.connected is False
    assert client.running is False
    assert client.socket is None


def test_network_client_notify_message_received_swallows_callback_errors():
    client = NetworkClient()
    client.on_message_received = lambda message: (_ for _ in ()).throw(RuntimeError("boom"))

    client._notify_message_received("PING")


def test_network_client_notify_message_received_swallows_zero_arg_callback_errors():
    client = NetworkClient()
    client.on_message_received = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    client._notify_message_received("PING")


def test_network_client_keepalive_loop_skips_send_when_disconnected(monkeypatch):
    client = NetworkClient()
    client.connected = False
    client.running = True
    sent = []
    monkeypatch.setattr(client, "send", lambda message: sent.append(message) or True)

    def stop_after_first_sleep(_delay):
        client.running = False

    monkeypatch.setattr(
        "amazons.controller.network.network_client.time.sleep",
        stop_after_first_sleep,
    )

    client._keepalive_loop()

    assert sent == []


def test_network_client_receive_loop_processes_timeout_message(monkeypatch):
    client = NetworkClient()
    client.running = True

    class TimeoutSocket:
        def settimeout(self, _timeout):
            return None

        def recv(self, _size):
            return b"TIMEOUT\n"

    client.socket = TimeoutSocket()
    disconnected = []
    monkeypatch.setattr(
        client,
        "disconnect",
        lambda: disconnected.append(True) or setattr(client, "running", False),
    )

    client._receive_loop()

    assert client.disconnect_reason == "Disconnected after 60 seconds of inactivity."
    assert client.receive() == "TIMEOUT"
    assert disconnected == [True]


def test_network_discovery_start_is_idempotent(monkeypatch):
    reloaded_module = importlib.reload(network_client_module)
    discovery = reloaded_module.NetworkDiscovery()
    started = []

    class DummyThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append(self.target.__name__)

    monkeypatch.setattr(
        reloaded_module.threading,
        "Thread",
        DummyThread,
    )

    discovery.start()
    discovery.start()

    assert started == ["_discovery_loop"]


def test_network_discovery_stop_joins_thread():
    reloaded_module = importlib.reload(network_client_module)
    discovery = reloaded_module.NetworkDiscovery()
    joined = []

    class DummyThread:
        def join(self, timeout):
            joined.append(timeout)

    discovery.running = True
    discovery.thread = DummyThread()
    discovery.stop()

    assert discovery.running is False
    assert joined == [1.0]


def test_network_discovery_loop_returns_when_bind_fails(monkeypatch):
    discovery = NetworkDiscovery()

    class BindFailSocket:
        def setsockopt(self, *args):
            return None

        def bind(self, addr):
            raise OSError("busy")

    monkeypatch.setattr(
        "amazons.controller.network.network_client.socket.socket",
        lambda *_args, **_kwargs: BindFailSocket(),
    )

    discovery._discovery_loop()


def test_network_discovery_loop_collects_server(monkeypatch):
    discovery = NetworkDiscovery()
    discovery.running = True
    timestamps = iter([100.0, 100.0, 100.0])

    class FakeSocket:
        def __init__(self):
            self.calls = 0
            self.closed = False

        def setsockopt(self, *args):
            return None

        def bind(self, addr):
            return None

        def settimeout(self, timeout):
            return None

        def recvfrom(self, _size):
            self.calls += 1
            if self.calls == 1:
                discovery.running = False
                return (b"Amazons:12345", ("127.0.0.1", 9999))
            raise socket.timeout()

        def close(self):
            self.closed = True

    fake_socket = FakeSocket()
    monkeypatch.setattr(
        "amazons.controller.network.network_client.socket.socket",
        lambda *_args, **_kwargs: fake_socket,
    )
    monkeypatch.setattr(
        "amazons.controller.network.network_client.time.time",
        lambda: next(timestamps),
    )

    discovery._discovery_loop()

    assert discovery.servers["127.0.0.1:12345"]["name"] == "Amazons"
    assert fake_socket.closed is True
