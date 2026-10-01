import base64
import builtins
from unittest.mock import MagicMock

from amazons.controller.engine.game_controller import GameController
from amazons.controller.save_load_manager import SaveLoadManager
from amazons.model.players.human_player import HumanPlayer
from amazons.model.players.player import NetworkPlayer


class MockCLI:
    def __init__(self):
        self.messages = []

    def msg(self, text):
        self.messages.append(text)

    def error(self, text):
        self.messages.append(text)

    def input_cli(self, prompt=""):
        return "Player"

    def show_board(self, board_array):
        return None

    def show_board_possible_moves(self, board_array, highlights):
        return None

    def show_history(self, history, size):
        return None

    def show_help(self):
        return None

    def welcome(self, size):
        return None

    def ask_opponent_type(self):
        return "hu"


def _make_controller(size=6):
    controller = GameController(size=size)
    controller.cli = MockCLI()
    controller.board.init_board()
    return controller


def test_wait_for_remote_client_requires_running_server():
    gc = _make_controller()

    assert gc._wait_for_remote_client(timeout=0.01) is False
    assert any("Start the server first" in msg for msg in gc.cli.messages)


def test_wait_for_remote_client_detects_connection_after_poll(monkeypatch):
    gc = _make_controller()
    gc.server.running = True
    gc.server.client_socket = None

    fake_times = iter([0.0, 0.0, 0.05])
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.time",
        lambda: next(fake_times),
    )

    def connect_after_sleep(_delay):
        gc.server.client_socket = object()

    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.sleep",
        connect_after_sleep,
    )

    assert gc._wait_for_remote_client(timeout=0.1, poll_interval=0.01) is True
    assert any("Waiting for remote player" in msg for msg in gc.cli.messages)
    assert any("Remote player connected." in msg for msg in gc.cli.messages)


def test_start_resumes_loaded_game_after_player_selection(monkeypatch):
    gc = _make_controller()
    gc.is_loaded_from_save = True
    resumed = []
    commands = iter(["quit"])
    monkeypatch.setattr(gc, "resolve_opponent_type", lambda parts: "hu")
    monkeypatch.setattr(gc, "resumeGame", lambda mode: resumed.append(mode))
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt=">> ": next(commands))
    monkeypatch.setattr(gc, "handle_quit", lambda in_game=False: "exit")
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert resumed == ["hu"]
    assert any("Save loaded." in msg for msg in gc.cli.messages)


def test_start_reports_gui_import_error(monkeypatch):
    gc = _make_controller()
    gc.use_gui = True
    messages = []
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "gi":
            raise ImportError("no gi")
        return original_import(name, globals, locals, fromlist, level)

    gc.cli.msg = lambda text: messages.append(text)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    gc.start()

    assert any("GUI unavailable" in msg for msg in messages)
    assert any("no gi" in msg for msg in messages)


def test_run_gui_presents_created_window():
    gc = _make_controller()
    presented = []

    class DummyWindow:
        def __init__(self, app, size, controller):
            self.app = app
            self.size = size
            self.controller = controller

        def present(self):
            presented.append((self.app, self.size, self.controller))

    gc._view_gui_class = DummyWindow
    gc.run_gui(app="APP")

    assert presented == [("APP", gc.size, gc)]


def test_start_handles_pending_network_host_start(monkeypatch):
    gc = _make_controller()
    started = []
    gc.pending_network_host_start = True
    gc.server.running = True
    gc.server.client_socket = object()
    commands = iter(["quit"])
    monkeypatch.setattr(gc, "startGame", lambda mode: started.append(mode))
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt=">> ": next(commands))
    monkeypatch.setattr(gc, "handle_quit", lambda in_game=False: "exit")
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert started == ["network"]
    assert gc.pending_network_host_start is False


def test_start_game_network_client_handles_black_local_player(monkeypatch):
    gc = _make_controller()
    gc.client.send = MagicMock(return_value=True)
    gc.client.inbox = ["NAME HostPlayer"]
    gc.cli.input_cli = lambda prompt="": "ClientPlayer"
    played = []
    monkeypatch.setattr(gc, "play_turn", lambda: played.append(True))
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.sleep",
        lambda _delay: None,
    )

    gc.startGame(
        "network_client",
        {"host_color": "B", "time_limit": 45.0},
    )

    assert played == [True]
    assert isinstance(gc.players[0], HumanPlayer)
    assert gc.players[0].color_code == "W"
    assert gc.players[0].nom == "HostPlayer"
    assert isinstance(gc.players[1], NetworkPlayer)
    assert gc.players[1].nom == "Remote"


def test_start_game_aborts_when_player_creation_fails(monkeypatch):
    gc = _make_controller()
    monkeypatch.setattr(gc, "create_players", lambda adversaire: False)
    monkeypatch.setattr(gc, "play_turn", lambda: (_ for _ in ()).throw(AssertionError("play_turn should not run")))

    gc.startGame("hu")

    assert gc.network_host_starting is False


def test_start_new_command_invites_known_player(monkeypatch):
    gc = _make_controller()
    handled = []
    commands = iter(["new P1", "quit"])
    gc.server.running = True
    gc.server.host_player = {"name": None, "status": "idle"}
    gc.server.request_invitation = lambda inviter, invitee: f"INVITE_SENT {invitee}"
    gc.cli.input_cli = lambda prompt="": "HostName"
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt=">> ": next(commands))
    monkeypatch.setattr(gc, "_handle_network_notification", lambda message: handled.append(message) or True)
    monkeypatch.setattr(gc, "handle_quit", lambda in_game=False: "exit")
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert handled == ["INVITE_SENT P1"]
    assert gc.server.host_player["name"] == "HostName"


def test_start_new_command_refuses_when_client_already_connected(monkeypatch):
    gc = _make_controller()
    gc.client.connected = True
    commands = iter(["new hu", "quit"])
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt=">> ": next(commands))
    monkeypatch.setattr(gc, "handle_quit", lambda in_game=False: "exit")
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert any("Already connected to a server." in msg for msg in gc.cli.messages)


def test_start_new_command_announces_selected_mode(monkeypatch):
    gc = _make_controller()
    commands = iter(["new ai", "quit"])
    started = []
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt=">> ": next(commands))
    monkeypatch.setattr(gc, "startGame", lambda mode: started.append(mode))
    monkeypatch.setattr(gc, "handle_quit", lambda in_game=False: "exit")
    monkeypatch.setattr(gc.discovery, "stop", lambda: None)
    monkeypatch.setattr(gc.server, "stop", lambda notify_client=False: None)

    gc.start()

    assert started == ["ai"]
    assert any("Starting new game against AI" in msg for msg in gc.cli.messages)


def test_wait_for_remote_client_times_out(monkeypatch):
    gc = _make_controller()
    gc.server.running = True
    gc.server.client_socket = None
    fake_times = iter([0.0, 0.05, 0.15])
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.time",
        lambda: next(fake_times),
    )
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.sleep",
        lambda _delay: None,
    )

    assert gc._wait_for_remote_client(timeout=0.1, poll_interval=0.01) is False
    assert any("No remote player connected yet" in msg for msg in gc.cli.messages)


def test_start_game_network_client_sets_colors_names_and_timers(monkeypatch):
    gc = _make_controller()
    gc.client.send = MagicMock(return_value=True)
    gc.client.inbox = ["NAME HostPlayer"]
    gc.cli.input_cli = lambda prompt="": "ClientPlayer"
    played = []
    monkeypatch.setattr(gc, "play_turn", lambda: played.append(True))
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.time.sleep",
        lambda _delay: None,
    )

    gc.startGame(
        "network_client",
        {"host_color": "W", "time_limit": 90.0},
    )

    assert played == [True]
    assert gc.time_limit_per_move == 90.0
    assert gc.timers == {"W": 90.0, "B": 90.0}
    assert isinstance(gc.players[0], NetworkPlayer)
    assert gc.players[0].nom == "HostPlayer"
    assert isinstance(gc.players[1], HumanPlayer)
    assert gc.players[1].nom == "ClientPlayer"
    assert gc.players[1].color_code == "B"
    gc.client.send.assert_called_once_with("NAME ClientPlayer")


def test_sync_loaded_game_to_remote_handles_missing_file():
    gc = _make_controller()
    gc.server.client_socket = object()

    assert gc._sync_loaded_game_to_remote("/definitely/missing/file.amz") is False
    assert any("Failed to read save file for sync" in msg for msg in gc.cli.messages)


def test_sync_loaded_game_to_remote_sends_base64_payload(tmp_path):
    gc = _make_controller()
    gc.server.client_socket = object()
    gc.server.send = MagicMock(return_value=True)
    filepath = tmp_path / "game.amz"
    filepath.write_text("example", encoding="utf-8")

    assert gc._sync_loaded_game_to_remote(str(filepath)) is True

    sent_message = gc.server.send.call_args.args[0]
    assert sent_message.startswith("LOAD_STATE ")
    payload = sent_message[len("LOAD_STATE "):]
    assert base64.b64decode(payload).decode("utf-8") == "example"


def test_sync_current_state_to_remote_without_client_is_noop():
    gc = _make_controller()

    assert gc.sync_current_state_to_remote() is True


def test_sync_current_state_to_remote_sends_current_snapshot():
    gc = _make_controller()
    gc.server.client_socket = object()
    gc.server.send = MagicMock(return_value=True)

    assert gc.sync_current_state_to_remote() is True
    sent_message = gc.server.send.call_args.args[0]
    assert sent_message.startswith("LOAD_STATE ")


def test_encode_current_state_for_sync_returns_decodable_payload():
    gc = _make_controller()

    payload = gc._encode_current_state_for_sync()
    decoded = base64.b64decode(payload).decode("utf-8")

    assert "[game]" in decoded
    assert "[history]" in decoded


def test_apply_remote_loaded_game_rejects_bad_base64():
    gc = _make_controller()

    assert gc._apply_remote_loaded_game("%%%") is False
    assert any("Failed to decode remote save" in msg for msg in gc.cli.messages)


def test_apply_remote_loaded_game_applies_valid_payload():
    gc = _make_controller()
    shown = []
    gc.cli.show_board = lambda board_array: shown.append(board_array)
    payload = base64.b64encode(
        SaveLoadManager.serialize_game_state(
            size=gc.size,
            time_limit_per_move=gc.time_limit_per_move,
            board=gc.board,
            history=[],
            ai_mode=gc.ai_mode,
            ai_time=gc.ai_time,
            ai_evaluator=gc.ai_evaluator,
        ).encode("utf-8")
    ).decode("ascii")

    assert gc._apply_remote_loaded_game(payload) is True
    assert gc.is_saved is True
    assert shown
    assert any("Game loaded successfully." in msg for msg in gc.cli.messages)
    assert any("Game state updated from host." in msg for msg in gc.cli.messages)


def test_handle_pending_network_event_starts_client_game(monkeypatch):
    gc = _make_controller()
    started = []
    gc.client.inbox = ["START 6 WHITE 90.0"]
    monkeypatch.setattr(
        gc,
        "startGame",
        lambda mode, params=None: started.append((mode, params)),
    )

    assert gc._handle_pending_network_event() == "started"
    assert gc.size == 6
    assert started == [("network_client", {"host_color": "WHITE", "time_limit": 90.0})]


def test_handle_pending_network_event_applies_load_state(monkeypatch):
    gc = _make_controller()
    gc.client.inbox = ["LOAD_STATE payload"]
    monkeypatch.setattr(gc, "_apply_remote_loaded_game", lambda payload: payload == "payload")

    assert gc._handle_pending_network_event() == "loaded"


def test_prompt_save_before_quit_handles_invalid_then_no():
    gc = _make_controller()
    gc.is_saved = False
    gc.history = [(MagicMock(), "W")]
    answers = iter(["maybe", ""])
    gc.cli.input_cli = lambda prompt="": next(answers)

    assert gc.prompt_save_before_quit() is True
    assert any("Please answer y or n." in msg for msg in gc.cli.messages)


def test_prompt_save_before_quit_retries_failed_save(monkeypatch):
    gc = _make_controller()
    gc.is_saved = False
    gc.history = [(MagicMock(), "W")]
    answers = iter(["yes", "bad.amz", "yes", "good.amz"])
    results = iter([(False, "save failed"), (True, "saved")])
    gc.cli.input_cli = lambda prompt="": next(answers)
    monkeypatch.setattr(
        SaveLoadManager,
        "save_game",
        lambda controller, filepath: next(results),
    )

    assert gc.prompt_save_before_quit() is True
    assert gc.is_saved is True
    assert "save failed" in gc.cli.messages
    assert "saved" in gc.cli.messages


def test_get_input_or_network_uses_plain_input_when_local(monkeypatch):
    gc = _make_controller()
    monkeypatch.setattr("builtins.input", lambda prompt="": "HeLp")

    assert gc._get_input_or_network(prompt=">> ") == "help"


def test_get_input_or_network_accepts_remote_undo_request(monkeypatch):
    gc = _make_controller()
    gc.server.running = True
    gc.server.inbox = ["UNDO_REQ W"]
    gc.server.send = MagicMock(return_value=True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    assert gc._get_input_or_network(prompt=">> ") == "NETWORK_EVENT"
    gc.server.send.assert_called_once_with("UNDO_OK")


def test_get_input_or_network_declines_remote_undo_request(monkeypatch):
    gc = _make_controller()
    gc.server.running = True
    gc.server.inbox = ["UNDO_REQ W"]
    gc.server.send = MagicMock(return_value=True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    class DummyStdin:
        def readline(self):
            return "quit\n"

    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.select.select",
        lambda _read, _write, _error, _timeout: ([DummyStdin()], [], []),
    )
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.sys.stdin",
        DummyStdin(),
    )

    assert gc._get_input_or_network(prompt=">> ") == "quit"
    gc.server.send.assert_called_once_with("UNDO_NO")


def test_get_input_or_network_returns_quit_game_for_remote_message():
    gc = _make_controller()
    gc.client.inbox = ["QUIT_GAME"]

    assert gc._get_input_or_network(prompt=">> ") == "QUIT_GAME"


def test_get_input_or_network_returns_quit_for_remote_session_close():
    gc = _make_controller()
    gc.client.inbox = ["QUIT"]

    assert gc._get_input_or_network(prompt=">> ") == "QUIT"


def test_get_input_or_network_returns_network_event_for_remote_load_state():
    gc = _make_controller()
    gc.client.inbox = ["LOAD_STATE payload"]

    assert gc._get_input_or_network(prompt=">> ") == "NETWORK_EVENT"


def test_get_input_or_network_returns_network_event_for_remote_gameover(capsys):
    gc = _make_controller()
    gc.client.inbox = ["GAMEOVER something happened"]

    assert gc._get_input_or_network(prompt=">> ") == "NETWORK_EVENT"
    captured = capsys.readouterr()
    assert "Game Over: something happened" in captured.out


def test_get_input_or_network_updates_remote_name_before_local_read(monkeypatch):
    gc = _make_controller()
    remote = NetworkPlayer("Remote", "B", MagicMock())
    gc.players = [HumanPlayer("Local", "", "W"), remote]
    gc.client.inbox = ["NAME HostName"]

    class DummyStdin:
        def readline(self):
            return "quit\n"

    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.select.select",
        lambda _read, _write, _error, _timeout: ([DummyStdin()], [], []),
    )
    monkeypatch.setattr(
        "amazons.controller.engine.game_controller.sys.stdin",
        DummyStdin(),
    )

    assert gc._get_input_or_network(prompt=">> ") == "quit"
    assert remote.nom == "HostName"


def test_handle_end_game_draw_reports_tie(monkeypatch):
    gc = _make_controller()
    gc.players = [
        HumanPlayer("Alice", "", "W"),
        HumanPlayer("Bob", "", "B"),
    ]
    monkeypatch.setattr(
        gc.board,
        "calculate_territory_scores",
        lambda: (3, 3),
    )

    gc.handle_end_game("Finished")

    assert any("ÉGALITÉ" in msg for msg in gc.cli.messages)


def test_handle_end_game_reports_black_win_when_white_loses_on_time(monkeypatch):
    gc = _make_controller()
    gc.players = [
        HumanPlayer("Alice", "", "W"),
        HumanPlayer("Bob", "", "B"),
    ]
    monkeypatch.setattr(
        gc.board,
        "calculate_territory_scores",
        lambda: (0, 0),
    )

    gc.handle_end_game("Timeout", loser_color="W")

    assert any("BLACK WINS" in msg for msg in gc.cli.messages)


def test_handle_end_game_reports_white_win_when_black_loses_on_time(monkeypatch):
    gc = _make_controller()
    gc.players = [
        HumanPlayer("Alice", "", "W"),
        HumanPlayer("Bob", "", "B"),
    ]
    monkeypatch.setattr(
        gc.board,
        "calculate_territory_scores",
        lambda: (0, 0),
    )

    gc.handle_end_game("Timeout", loser_color="B")

    assert any("WHITE WINS" in msg for msg in gc.cli.messages)


def test_handle_end_game_blocked_player_reports_winner(monkeypatch):
    gc = _make_controller()
    gc.players = [
        HumanPlayer("Alice", "", "W"),
        HumanPlayer("Bob", "", "B"),
    ]
    monkeypatch.setattr(
        gc.board,
        "calculate_territory_scores",
        lambda: (1, 2),
    )

    gc.handle_end_game("Bob is blocked!")

    assert any("WHITE WINS" in msg for msg in gc.cli.messages)
