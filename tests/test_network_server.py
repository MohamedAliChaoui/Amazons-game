import base64

from amazons.controller.network.network_server import NetworkServer
from amazons.model.board.board import Board
from amazons.model.board.move import Move


def _make_session_history(size=6):
    board = Board(size)
    move_w = Move(
        Move.from_algebraic("c6", size),
        Move.from_algebraic("c5", size),
        Move.from_algebraic("b5", size),
    )
    board.make_move(move_w, "W")
    move_b = Move(
        Move.from_algebraic("d1", size),
        Move.from_algebraic("d2", size),
        Move.from_algebraic("e2", size),
    )
    board.make_move(move_b, "B")
    return board, [(move_w, "W"), (move_b, "B")]


def test_client_session_undo_reply_broadcasts_synced_state():
    server = NetworkServer()
    board, history = _make_session_history()
    session_id = "S1"
    session = {
        "id": session_id,
        "size": 6,
        "time_limit": 1800.0,
        "board": board,
        "history": history,
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

    sent = []
    server._notify_actor = lambda pid, msg: sent.append((pid, msg)) or True

    server._handle_client_session_undo_request(session_id, "P1", "UNDO_REQ W")
    assert session["pending_undo_requester_id"] == "P1"
    assert session["pending_undo_requester_color"] == "W"

    server._handle_client_session_undo_reply(session_id, "P2", accepted=True)

    assert session["pending_undo_requester_id"] is None
    assert session["pending_undo_requester_color"] is None
    assert session["pending_undo_requested_at"] is None
    assert session["history"] == []

    sync_messages = [msg for _pid, msg in sent if msg.startswith("LOAD_STATE ")]
    assert len(sync_messages) == 2
    payload = sync_messages[0][11:].strip()
    decoded = base64.b64decode(payload).decode("utf-8")
    assert "[game]" in decoded
    assert "[history]" in decoded

    requester_messages = [msg for pid, msg in sent if pid == "P1"]
    assert requester_messages[-1] == "UNDO_OK"


def test_client_session_undo_request_expires_stale_pending_request():
    server = NetworkServer()
    board, history = _make_session_history()
    session_id = "S1"
    session = {
        "id": session_id,
        "size": 6,
        "time_limit": 1800.0,
        "board": board,
        "history": history,
        "players": {"W": "P1", "B": "P2"},
        "player_colors": {"P1": "W", "P2": "B"},
        "names": {"W": "White", "B": "Black"},
        "pending_undo_requester_id": "P1",
        "pending_undo_requester_color": "W",
        "pending_undo_requested_at": -100.0,
    }
    server.active_sessions[session_id] = session
    server.player_sessions["P1"] = session_id
    server.player_sessions["P2"] = session_id

    sent = []
    server._notify_actor = lambda pid, msg: sent.append((pid, msg)) or True

    server._handle_client_session_undo_request(session_id, "P2", "UNDO_REQ B")

    assert session["pending_undo_requester_id"] == "P2"
    assert session["pending_undo_requester_color"] == "B"
    assert sent == [("P1", "UNDO_REQ B")]
