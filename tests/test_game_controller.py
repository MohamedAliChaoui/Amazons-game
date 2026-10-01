import base64
import pytest
import time
import math
from unittest.mock import MagicMock, patch
from amazons.controller.save_load_manager import SaveLoadManager
from amazons.controller.engine.game_controller import GameController
from amazons.model.board.move import Move
from amazons.model.players.human_player import HumanPlayer
from amazons.model.players.ai_player import AIPlayer
from amazons.model.players.player import NetworkPlayer

class MockCLI:
    def __init__(self):
        self.messages = []

    def msg(self, text):
        self.messages.append(text)

    def error(self, text):
        self.messages.append(text)

    def input_cli(self, prompt=""):
        return "TestPlayer"

    def show_board(self, board_array):
        pass

    def show_board_possible_moves(self, board_array, highlights):
        pass

    def show_history(self, history, size):
        pass

    def show_help(self):
        pass

    def welcome(self, size):
        pass

    def ask_opponent_type(self):
        return "hu"

@pytest.fixture
def gc():
    c = GameController()
    c.cli = MockCLI()
    c.board.init_board()
    return c

@pytest.mark.parametrize("args, expected_attr, expected_val, expected_msg", [
    (["set", "ai-mode", "random"], "ai_mode", "random", "ai-mode set to random"),
    (["set", "ai-time", "12.5"], "ai_time", 12.5, "ai-time set to 12.5"),
    (["set", "ai-depth", "5"], "ai_depth", 5, "ai-depth set to 5"),
    (["set", "ai-evaluator", "territory"], "ai_evaluator", "territory", "ai-evaluator set to territory"),
    (["set", "ai-time", "abc"], "ai_time", 5.0, "ai-time must be a number."),
    (["set", "ai-mode", "super_ai"], "ai_mode", "minimax", "Invalid AI mode"),
    (["set", "ai-depth", "not_int"], "ai_depth", 3, "ai-depth must be an integer"),
    (["set", "ai-mode"], "ai_mode", "minimax", "Usage: set <param>=<value>"),
])
def test_handle_set_command(gc, args, expected_attr, expected_val, expected_msg):
    gc.handle_set_command(args)
    assert getattr(gc, expected_attr) == expected_val
    assert any(expected_msg in m for m in gc.cli.messages)

def test_pause_state(gc):
    assert gc.is_paused == False
    gc.is_paused = True
    assert gc.is_paused == True

@pytest.mark.parametrize("args, expected_msg", [
    (["sb"], None),
    (["show", "board"], None),
    (["show", "history"], None),
    (["show", "time"], None),
    (["show", "configuration"], "Configuration:"),
    (["show", "invalid"], "Unknown show command"),
    (["show", "future"], "Unknown show command"),
])
def test_handle_show_command(gc, args, expected_msg):
    gc.timers = {"W": 300, "B": 300}
    if args == ["show", "time"]:
        gc.is_start_party = True

    res = gc.handle_show_command(args)
    assert res is True
    if expected_msg:
        assert any(expected_msg in m for m in gc.cli.messages)

@pytest.mark.parametrize("args, expected", [
    (["new", "hu"], "hu"),
    (["new", "ai"], "ai"),
    (["new", "aiai"], "aiai"),
    (["new", "network"], "network"),
    (["new", "invalid"], None),
])
def test_resolve_opponent_type(gc, args, expected):
    assert gc.resolve_opponent_type(args) == expected

def test_create_players():
    gc = GameController()
    gc.cli = MockCLI()

    gc.create_players("hu")
    assert len(gc.players) == 2
    assert isinstance(gc.players[0], HumanPlayer)
    assert isinstance(gc.players[1], HumanPlayer)

    gc.create_players("ai")
    assert isinstance(gc.players[0], HumanPlayer)

def test_handle_hint_command(gc, monkeypatch):
    from amazons.model.ai.mcts_engine import MCTSEngine
    from amazons.model.ai.iterative_deepening import IterativeDeepening

    monkeypatch.setattr(MCTSEngine, "best_move", lambda *args: "a1-a2/a3")
    monkeypatch.setattr(IterativeDeepening, "best_move", lambda *args: "a1-a2/a3")

    for mode in ["random", "mcts", "iterative", "minimax"]:
        gc.ai_mode = mode
        gc.ai_time = 0.01
        gc.handle_hint_command("W")
        assert any("Hint" in m for m in gc.cli.messages)

@pytest.mark.parametrize("mode, input_val, expected_types, expected_names", [
    ("hu", "Ali,Ch", ["HumanPlayer", "HumanPlayer"], ["Ali", "Ali"]),
    ("ai", "Ali,Ch", ["HumanPlayer", "AIPlayer"], ["Ali", "AIBot[minimax]"]),
    ("aiai", None, ["AIPlayer", "AIPlayer"], ["AIBotWhite[minimax]", "AIBotBlack[minimax]"]),
])
def test_create_players(gc, mode, input_val, expected_types, expected_names):
    if input_val:
        gc.cli.input_cli = lambda prompt="": input_val

    gc.create_players(mode)
    assert len(gc.players) == 2
    for i, (t_name, n_name) in enumerate(zip(expected_types, expected_names)):
        assert type(gc.players[i]).__name__ == t_name
        assert gc.players[i].nom == n_name

def test_create_players_network(gc):
    gc.server = MagicMock()
    gc.server.client_socket = True
    gc.server.inbox = ["NAME RemoteBot"]
    gc.server.send.return_value = True
    gc.cli.input_cli = lambda prompt="": "HostName"

    assert gc.create_players("network") == True
    assert gc.players[0].nom == "HostName"
    assert gc.players[1].nom == "RemoteBot"

def test_create_players_network_reuses_existing_host_name(gc):
    gc.server = MagicMock()
    gc.server.client_socket = True
    gc.server.inbox = ["NAME RemoteBot"]
    gc.server.send.return_value = True
    gc.server.host_player = {"name": "StoredHost", "status": "idle"}
    prompts = []
    gc.cli.input_cli = lambda prompt="": prompts.append(prompt) or "Ignored"

    assert gc.create_players("network") == True
    assert gc.players[0].nom == "StoredHost"
    assert prompts == []

def test_undo_redo_empty_history(gc):
    gc.create_players("hu")
    gc.cli.input_cli = lambda prompt="": "yes"
    gc.undo_turn(gc.players[0], gc.players[1])
    assert "Nothing to undo" in gc.cli.messages[-1]

def test_handle_end_game(gc):
    gc.create_players("hu")
    with pytest.raises(SystemExit) if hasattr(gc, 'handle_end_game_exit') else patch('sys.exit'):
        try:
            gc.handle_end_game("Time over!", loser_color="W")
        except SystemExit:
            pass

@pytest.mark.parametrize("action, white_bb, expected_res, expected_msg", [
    ("move d10-d9", 1 << 3, True, None),
    ("move e2e4", 0, False, "Format invalide"),
    ("move z1-e4", 0, False, "Invalid coordinates"),
    ("move d10-e8", 1 << 3, False, "Queen move invalid"),
])
def test_handle_two_step_move(gc, action, white_bb, expected_res, expected_msg):
    p1 = HumanPlayer("Ali", "B", "W")
    gc._get_input_or_network = lambda prompt="", timeout_check=None: "d4"
    gc.board.white_bb = white_bb

    res = gc.handle_two_step_move(p1, action)
    assert res == expected_res
    if expected_msg:
        assert any(expected_msg in m for m in gc.cli.messages)

def test_undo_turn_with_history(gc):
    p1 = HumanPlayer("Ali", "B", "W")
    p2 = HumanPlayer("Bob", "C", "B")
    gc.players = [p1, p2]
    gc.history.append((Move(3, 13, 3), "W"))
    gc.cli.input_cli = lambda prompt="": "yes"

    assert gc.undo_turn(p1, p2) == True
    assert len(gc.history) == 0
    assert len(gc.redo_history) == 1

def test_resolve_opponent_type_ask(gc):
    gc.cli.ask_opponent_type = lambda: "ai"
    assert gc.resolve_opponent_type(["new"]) == "ai"

def test_handle_save_load_triggers(gc, monkeypatch):
    from amazons.controller.save_load_manager import SaveLoadManager
    save_called, load_called = [], []
    monkeypatch.setattr(SaveLoadManager, "save_game", lambda c, f: (save_called.append(f), ("Saved"))[1])
    monkeypatch.setattr(SaveLoadManager, "load_game", lambda c, f: (load_called.append(f), setattr(c, "is_loaded_from_save", True), ("Loaded"))[2])

    SaveLoadManager.save_game(gc, "test_save.txt")
    assert "test_save.txt" in save_called
    SaveLoadManager.load_game(gc, "test_save.txt")
    assert gc.is_loaded_from_save == True

def test_start_loop_simple_commands(gc, monkeypatch):
    gc.discovery, gc.server, gc.client = MagicMock(), MagicMock(), MagicMock()
    gc.client.connected = gc.server.running = False
    cmds = ["help", "sb", "history", "quit"]
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: cmds.pop(0) if cmds else "quit")
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.start()
    assert "Bye!" in gc.cli.messages[-1]

def test_play_turn_mini_loop(gc, monkeypatch):
    gc.create_players("hu")
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: "quit")
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.play_turn()
    assert True

def test_ai_turn_logic(gc, monkeypatch):
    gc.ai_mode = "random"
    gc.create_players("ai")
    gc.history.append((MagicMock(), "W"))
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: "quit")
    monkeypatch.setattr(time, "sleep", lambda x: None)
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.play_turn()
    assert len(gc.history) == 2

def test_startGame_basic(gc, monkeypatch):
    gc.cli.input_cli = lambda prompt="": "Ali,Ch"
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: "quit")
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.startGame("hu")
    assert gc.is_start_party == True
    assert len(gc.players) == 2


def test_play_turn_allows_players_command(gc, monkeypatch):
    gc.create_players("hu")
    commands = iter(["players", "quit"])

    gc.server.get_players = lambda: [
        {
            "id": "P1",
            "name": "Remote",
            "status": "idle",
            "address": ("127.0.0.1", 12345),
        }
    ]
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: next(commands))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)

    gc.play_turn()

    assert any("P1: Remote | idle | 127.0.0.1:12345" in m for m in gc.cli.messages)


def test_play_turn_handles_network_event_token(gc, monkeypatch):
    gc.create_players("hu")
    commands = iter(["NETWORK_EVENT", "quit"])
    handled = []

    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: next(commands))
    monkeypatch.setattr(gc, "_handle_pending_network_event", lambda: handled.append(True) or "pending")
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)

    gc.play_turn()

    assert handled == [True]
    assert not any("Action invalide" in m for m in gc.cli.messages)


def test_play_turn_prompts_save_on_remote_quit_game_for_host(gc, monkeypatch):
    gc.create_players("hu")
    gc.server.running = True
    gc.history.append((MagicMock(), "W"))
    gc.is_saved = False
    prompted = []
    closed = []

    monkeypatch.setattr(
        gc, "_get_input_or_network",
        lambda prompt="", timeout_check=None: "QUIT_GAME"
    )
    monkeypatch.setattr(
        gc, "prompt_save_before_quit", lambda: prompted.append(True) or True
    )
    monkeypatch.setattr(
        gc, "close_network_session",
        lambda notify_remote=False: closed.append(notify_remote)
    )

    gc.play_turn()

    assert prompted == [True]
    assert closed == [False]
    assert any("Remote player quit the game." in m for m in gc.cli.messages)


def test_play_turn_skips_save_on_remote_quit_game_for_client(gc, monkeypatch):
    gc.create_players("hu")
    gc.client.connected = True
    gc.history.append((MagicMock(), "W"))
    gc.is_saved = False
    prompted = []
    closed = []

    monkeypatch.setattr(
        gc, "_get_input_or_network",
        lambda prompt="", timeout_check=None: "QUIT_GAME"
    )
    monkeypatch.setattr(
        gc, "prompt_save_before_quit", lambda: prompted.append(True) or True
    )
    monkeypatch.setattr(
        gc, "close_network_session",
        lambda notify_remote=False: closed.append(notify_remote)
    )

    gc.play_turn()

    assert prompted == []
    assert closed == [False]
    assert any("Remote player quit the game." in m for m in gc.cli.messages)


def test_network_player_turn_skips_save_on_remote_quit_for_client(gc, monkeypatch):
    gc.client.connected = True
    gc.players = [
        HumanPlayer("Host", "", "W"),
        NetworkPlayer("Remote", "B", gc.client),
    ]
    gc.history.append((MagicMock(), "W"))
    gc.is_saved = False
    prompted = []
    closed = []

    monkeypatch.setattr(gc.players[1], "get_action", lambda _board: "QUIT_GAME")
    monkeypatch.setattr(
        gc, "prompt_save_before_quit", lambda: prompted.append(True) or True
    )
    monkeypatch.setattr(
        gc, "close_network_session",
        lambda notify_remote=False: closed.append(notify_remote)
    )

    gc.play_turn()

    assert prompted == []
    assert closed == [False]
    assert any("Remote player quit the game." in m for m in gc.cli.messages)


def test_handle_network_notification_player_connected_shows_join_guidance(gc):
    assert gc._handle_network_notification("PLAYER_CONNECTED P1 Player1") is True
    assert any("new PLAYER_ID" in m for m in gc.cli.messages)


def test_remote_network_client_without_connection_still_skips_save_prompt(gc, monkeypatch):
    gc.players = [
        NetworkPlayer("Remote", "W", gc.client),
        HumanPlayer("Local", "", "B"),
    ]
    gc.history.append((MagicMock(), "W"))
    gc.is_saved = False
    prompted = []

    monkeypatch.setattr(
        gc, "prompt_save_before_quit", lambda: prompted.append(True) or True
    )

    assert gc._should_prompt_save_before_quit() is False
    assert prompted == []


def test_play_turn_uses_handle_quit_for_local_quit(gc, monkeypatch):
    gc.create_players("hu")
    results = []

    monkeypatch.setattr(
        gc, "_get_input_or_network",
        lambda prompt="", timeout_check=None: "quit"
    )
    monkeypatch.setattr(
        gc, "handle_quit",
        lambda in_game=False: results.append(in_game) or "disconnect"
    )

    gc.play_turn()

    assert results == [True]


def test_should_prompt_save_before_quit_uses_network_host_role(gc):
    gc.history.append((MagicMock(), "W"))
    gc.is_saved = False
    gc.players = [
        HumanPlayer("Host", "", "W"),
        NetworkPlayer("Remote", "B", gc.client),
    ]
    gc.server.running = True
    gc.client.connected = True

    assert gc._should_prompt_save_before_quit() is True

    gc.server.running = False

    assert gc._should_prompt_save_before_quit() is False


def test_play_turn_sends_clock_update_before_network_move(gc, monkeypatch):
    gc.create_players("hu")
    gc.client.connected = True
    sent_clock_colors = []
    sent_messages = []
    commands = iter(["move", "quit"])
    move = Move(
        Move.from_algebraic("d1", gc.size),
        Move.from_algebraic("d2", gc.size),
        Move.from_algebraic("d3", gc.size),
    )

    def fake_move(_joueur, _action):
        gc.history.append((move, "W"))
        return True

    monkeypatch.setattr(
        gc, "_get_input_or_network",
        lambda prompt="", timeout_check=None: next(commands)
    )
    monkeypatch.setattr(gc, "handle_two_step_move", fake_move)
    monkeypatch.setattr(gc, "_send_clock_update", lambda color: sent_clock_colors.append(color) or True)
    monkeypatch.setattr(gc.client, "send", lambda msg: sent_messages.append(msg) or True)
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)

    gc.play_turn()

    assert sent_clock_colors == ["W"]
    assert sent_messages[0] == "MOVE Wd1-d2/d3"


def test_handle_network_notification_ignores_duplicate_host_start(gc, monkeypatch):
    started = []
    gc.is_start_party = True
    gc.network_host_starting = False
    monkeypatch.setattr(gc, "startGame", lambda mode: started.append(mode))

    assert gc._handle_network_notification("HOST_START_GAME P1") is True
    assert started == []
    assert not any("Starting network game" in m for m in gc.cli.messages)

def test_handle_pending_network_event_uses_stable_server_inbox(gc):
    class FlakyServer:
        def __init__(self):
            self.running = True
            self._messages = [["HOST_START_GAME P1"], []]
            self.active_player_id = None

        @property
        def inbox(self):
            if self._messages:
                return self._messages.pop(0)
            return []

    gc.server = FlakyServer()
    gc.client = MagicMock(connected=False)
    gc.network_host_starting = True
    gc.is_start_party = False
    gc.startGame = lambda mode: None

    assert gc._handle_pending_network_event() == "server_event"

def test_handle_pending_network_event_processes_server_stop_after_disconnect(gc):
    class PendingClient:
        def __init__(self):
            self.connected = False
            self.disconnect_reason = "Server stopped and closed the session."
            self._pending = ["SERVER_STOP"]
            self.on_message_received = None

        @property
        def inbox(self):
            return self._pending

        @inbox.setter
        def inbox(self, messages):
            self._pending = list(messages)

    gc.server = MagicMock(running=False)
    gc.client = PendingClient()

    assert gc._handle_pending_network_event() == "client_event"
    assert any(
        "Server stopped and closed the session." in msg
        for msg in gc.cli.messages
    )


def test_show_scoreboard_reports_empty_state(gc):
    gc.server.get_scoreboard = lambda: []

    gc.show_scoreboard()

    assert gc.cli.messages[-1] == "Scoreboard is empty."


def test_handle_end_game_updates_network_scoreboard(gc):
    from amazons.model.players.human_player import HumanPlayer

    gc.players = [
        HumanPlayer("HostPlayer", "", "white"),
        HumanPlayer("RemotePlayer", "", "black"),
    ]
    gc.server.active_player_id = "P1"
    gc.server.connected_players = {
        "P1": {
            "id": "P1",
            "name": "RemotePlayer",
            "status": "ingame",
            "address": ("127.0.0.1", 12345),
            "socket": None,
        }
    }
    gc.server.set_host_player("HostPlayer", status="ingame")

    gc.handle_end_game("HostPlayer is blocked!", loser_color="black")

    scoreboard = gc.server.get_scoreboard()
    assert scoreboard == [
        {"name": "HostPlayer", "wins": 1, "losses": 0, "played": 1},
        {"name": "RemotePlayer", "wins": 0, "losses": 1, "played": 1},
    ]


def test_show_players_detail_for_known_player(gc):
    gc.server.get_player = lambda player_id: {
        "id": player_id,
        "name": "Remote",
        "status": "idle",
        "address": ("127.0.0.1", 4567),
    }

    gc.show_players("p1")

    assert gc.cli.messages[-1] == "Player P1: Remote | idle | 127.0.0.1:4567"


def test_show_server_status_replaces_missing_active_player(gc):
    gc.server.get_status = lambda: {
        "port": 12345,
        "connected_clients": 0,
        "parties_in_progress": 0,
        "active_player_id": None,
    }

    gc.show_server_status()

    assert any("Active player: -" in msg for msg in gc.cli.messages)


def test_handle_network_notification_handles_timeout_message(gc):
    gc.client.disconnect_reason = "Disconnected after 60 seconds of inactivity."
    gc.is_start_party = True
    gc.pending_network_host_start = True
    gc.network_host_starting = True

    assert gc._handle_network_notification("TIMEOUT") is True
    assert gc.is_start_party is False
    assert gc.pending_network_host_start is False
    assert gc.network_host_starting is False
    assert gc.cli.messages[-1] == "Disconnected after 60 seconds of inactivity."


def test_start_game_network_failure_clears_pending_host_start(gc, monkeypatch):
    gc.pending_network_host_start = True
    monkeypatch.setattr(gc, "_wait_for_remote_client", lambda: False)

    gc.startGame("network")

    assert gc.pending_network_host_start is False
    assert gc.network_host_starting is False


def test_handle_quit_returns_exit_without_network(gc, monkeypatch):
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)

    assert gc.handle_quit(in_game=False) == "exit"


def test_handle_quit_skips_save_prompt_for_network_client(gc, monkeypatch):
    gc.client.connected = True
    gc.history.append((MagicMock(), "W"))
    gc.is_saved = False
    prompted = []

    monkeypatch.setattr(
        gc, "prompt_save_before_quit", lambda: prompted.append(True) or True
    )
    monkeypatch.setattr(gc, "close_network_session", lambda notify_remote=False: None)

    assert gc.handle_quit(in_game=True) == "disconnect"
    assert prompted == []
# ── Move validation ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("coord, size, exc_fragment", [
    ("",    10, "too short"),
    ("a",   10, "too short"),
    ("1a",  10, "invalid column letter"),
    ("ax",  10, "invalid row number"),
    ("z1",  10, "out of bounds"),
    ("a0",  10, "out of bounds"),
    ("a11", 10, "out of bounds"),
])
def test_from_algebraic_invalid(coord, size, exc_fragment):
    with pytest.raises(ValueError, match=exc_fragment):
        Move.from_algebraic(coord, size)

def test_from_algebraic_valid():
    assert Move.from_algebraic("a10", 10) == 0
    assert Move.from_algebraic("j1",  10) == 99

def test_to_algebraic_out_of_bounds():
    with pytest.raises(ValueError, match="out of bounds"):
        Move.to_algebraic(-1, 10)
    with pytest.raises(ValueError, match="out of bounds"):
        Move.to_algebraic(100, 10)

def test_to_algebraic_valid():
    assert Move.to_algebraic(0,  10) == "a10"
    assert Move.to_algebraic(99, 10) == "j1"

# ── redo_turn ─────────────────────────────────────────────────────────────────

def test_redo_turn_empty(gc):
    p1 = HumanPlayer("Ali", "A", "W")
    gc.players = [p1, HumanPlayer("Bob", "B", "B")]
    assert gc.redo_turn(p1) is False
    assert any("Nothing to redo" in m for m in gc.cli.messages)

def test_redo_turn_opponent_at_front(gc):
    p1 = HumanPlayer("Ali", "A", "W")
    p2 = HumanPlayer("Bob", "B", "B")
    gc.players = [p1, p2]
    gc.redo_history = [(Move(3, 4, 5), "B"), (Move(0, 1, 2), "W")]
    assert gc.redo_turn(p1) is False
    assert any("wait for your opponent" in m for m in gc.cli.messages)
    assert len(gc.redo_history) == 2

def test_redo_turn_human_vs_human(gc):
    p1 = HumanPlayer("Ali", "A", "W")
    p2 = HumanPlayer("Bob", "B", "B")
    gc.players = [p1, p2]
    gc.redo_history = [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]
    assert gc.redo_turn(p1) is True
    # Symmetric redo: full round restored (W + opponent B)
    assert gc.history == [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]
    assert gc.redo_history == []

def test_redo_turn_human_vs_ai(gc):
    p1 = HumanPlayer("Ali", "A", "W")
    ai = AIPlayer("AI", "B", "B")
    gc.players = [p1, ai]
    gc.redo_history = [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]
    assert gc.redo_turn(p1) is True
    assert gc.history == [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]
    assert gc.redo_history == []

def test_redo_turn_trailing_ai_moves(gc):
    p1 = HumanPlayer("Ali", "A", "W")
    ai = AIPlayer("AI", "B", "B")
    gc.players = [p1, ai]
    gc.redo_history = [
        (Move(0, 1, 2), "W"),
        (Move(3, 4, 5), "B"),
        (Move(6, 7, 8), "B"),
    ]
    assert gc.redo_turn(p1) is True
    assert len(gc.history) == 3
    assert gc.redo_history == []

def test_redo_turn_network_not_supported(gc):
    p1 = HumanPlayer("Ali", "A", "W")
    remote = NetworkPlayer("Remote", "B", MagicMock())
    gc.players = [p1, remote]
    gc.redo_history = [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]

    assert gc.redo_turn(p1) is False
    assert gc.history == []
    assert len(gc.redo_history) == 2
    assert any(
        "Redo is not supported in network games." in m
        for m in gc.cli.messages
    )

# ── undo_turn — NetworkPlayer paths ──────────────────────────────────────────

def test_undo_turn_network_undo_ok_via_server(gc, monkeypatch):
    p1 = MagicMock(couleur="W", color_code="W")
    remote = NetworkPlayer("Remote", "B", MagicMock())
    gc.players = [p1, remote]
    gc.history = [(Move(0, 1, 2), "W")]
    gc.server.client_socket = True
    gc.server.send = MagicMock(return_value=True)
    gc.server.receive = MagicMock(return_value="UNDO_OK")
    monkeypatch.setattr(time, "sleep", lambda x: None)
    assert gc.undo_turn(p1, remote) is True
    assert gc.history == []
    assert any("Requesting undo" in m for m in gc.cli.messages)
    sent_messages = [call.args[0] for call in gc.server.send.call_args_list]
    assert sent_messages[0] == "UNDO_REQ W"
    assert sent_messages[1].startswith("LOAD_STATE ")

def test_undo_turn_network_undo_no_via_client(gc, monkeypatch):
    p1 = MagicMock(couleur="W", color_code="W")
    remote = NetworkPlayer("Remote", "B", MagicMock())
    gc.players = [p1, remote]
    gc.history = [(Move(0, 1, 2), "W")]
    gc.server.client_socket = None
    gc.client.connected = True
    gc.client.receive = MagicMock(return_value="UNDO_NO")
    monkeypatch.setattr(time, "sleep", lambda x: None)
    assert gc.undo_turn(p1, remote) is False
    assert any("refused by remote" in m for m in gc.cli.messages)


def test_undo_turn_network_undo_ok_waits_for_synced_state(gc, monkeypatch):
    p1 = MagicMock(couleur="W", color_code="W")
    remote = NetworkPlayer("Remote", "B", MagicMock())
    gc.players = [p1, remote]
    gc.history = [(Move(0, 1, 2), "W")]
    gc.server.client_socket = None
    gc.client.connected = True
    sync_payload = base64.b64encode(
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
    gc.client.receive = MagicMock(
        side_effect=[
            "UNDO_OK",
            f"LOAD_STATE {sync_payload}",
        ]
    )
    monkeypatch.setattr(time, "sleep", lambda x: None)
    assert gc.undo_turn(p1, remote) is True
    assert gc.history == []

def test_undo_turn_network_timeout(gc, monkeypatch):
    p1 = MagicMock(couleur="W", color_code="W")
    remote = NetworkPlayer("Remote", "B", MagicMock())
    gc.players = [p1, remote]
    gc.history = [(Move(0, 1, 2), "W")]
    gc.server.client_socket = True
    gc.server.receive = MagicMock(return_value=None)
    times = iter([0, 31])
    monkeypatch.setattr("amazons.controller.engine.game_controller.time.time", lambda: next(times))
    monkeypatch.setattr(time, "sleep", lambda x: None)
    assert gc.undo_turn(p1, remote) is False
    assert any("timed out" in m for m in gc.cli.messages)


# ── undo_remote_requested ────────────────────────────────────────────────────

def test_undo_turn_remote_requested_with_history(gc):
    gc.history = [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]
    gc.undo_remote_requested()
    assert len(gc.history) == 1
    assert gc.redo_history == [(Move(3, 4, 5), "B")]

def test_undo_turn_remote_requested_empty(gc):
    gc.undo_remote_requested()
    assert gc.history == []
    assert gc.redo_history == []

def test_undo_turn_remote_requested_batch_until_requester(gc):
    """With requester_color, undo must pop the full round (both moves)
    so the local board mirrors what the remote requester sees."""
    gc.history = [
        (Move(0, 1, 2), "W"),
        (Move(3, 4, 5), "B"),
        (Move(6, 7, 8), "W"),
        (Move(9, 10, 11), "B"),
    ]
    gc.undo_remote_requested(requester_color="W")
    # Should pop B then W (one full round) and stop
    assert len(gc.history) == 2
    assert gc.history[-1] == (Move(3, 4, 5), "B")
    assert len(gc.redo_history) == 2
    assert gc.redo_history[0] == (Move(6, 7, 8), "W")
    assert gc.redo_history[1] == (Move(9, 10, 11), "B")

def test_undo_turn_remote_requested_batch_requester_black(gc):
    """Same batch logic when the remote requester is Black."""
    gc.history = [
        (Move(0, 1, 2), "W"),
        (Move(3, 4, 5), "B"),
        (Move(6, 7, 8), "W"),
    ]
    gc.undo_remote_requested(requester_color="B")
    # Pops W (top) then B → stops at B (requester's color)
    assert len(gc.history) == 1
    assert gc.history[-1] == (Move(0, 1, 2), "W")
    assert len(gc.redo_history) == 2


# ── _parse_repeat_count ──────────────────────────────────────────────────────

@pytest.mark.parametrize("parts, expected", [
    (["undo"], 1),
    (["undo", "1"], 1),
    (["undo", "3"], 3),
    (["redo", "10"], 10),
])
def test_parse_repeat_count_valid(gc, parts, expected):
    assert gc._parse_repeat_count(parts) == expected

@pytest.mark.parametrize("parts", [
    ["undo", "abc"],
    ["undo", "0"],
    ["undo", "-1"],
    ["undo", "1.5"],
    ["undo", ""],
])
def test_parse_repeat_count_invalid(gc, parts):
    assert gc._parse_repeat_count(parts) is None
    assert any("Invalid count" in m for m in gc.cli.messages)


# ── undo N / redo N batched behavior ─────────────────────────────────────────

def test_undo_n_calls_undo_turn_n_times(gc, monkeypatch):
    """undo 3 must invoke undo_turn three times (consent each time)."""
    p1 = HumanPlayer("Ali", "A", "W")
    p2 = HumanPlayer("Bob", "B", "B")
    gc.players = [p1, p2]
    gc.history = [
        (Move(0, 1, 2), "W"),
        (Move(3, 4, 5), "B"),
        (Move(6, 7, 8), "W"),
        (Move(9, 10, 11), "B"),
        (Move(12, 13, 14), "W"),
        (Move(15, 16, 17), "B"),
    ]
    gc.timers = {"W": 600, "B": 600}
    call_count = {"n": 0}
    real_undo = gc.undo_turn
    def counting(joueur, adversaire):
        call_count["n"] += 1
        return real_undo(joueur, adversaire)
    monkeypatch.setattr(gc, "undo_turn", counting)
    # Auto-consent: input_cli returns "yes" so consent always granted
    gc.cli.input_cli = lambda prompt="": "yes"
    # Drive only the undo branch by feeding a single command
    inputs = iter(["undo 3", "quit"])
    monkeypatch.setattr(gc, "_get_input_or_network",
                        lambda prompt="", timeout_check=None: next(inputs))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.play_turn()
    assert call_count["n"] == 3
    # 6 moves → 3 rounds undone → empty history
    assert len(gc.history) == 0

def test_redo_n_calls_redo_turn_n_times(gc, monkeypatch):
    """redo 2 must invoke redo_turn twice in HvH (each round restored)."""
    p1 = HumanPlayer("Ali", "A", "W")
    p2 = HumanPlayer("Bob", "B", "B")
    gc.players = [p1, p2]
    gc.history = []
    gc.redo_history = [
        (Move(0, 1, 2), "W"),
        (Move(3, 4, 5), "B"),
        (Move(6, 7, 8), "W"),
        (Move(9, 10, 11), "B"),
    ]
    gc.timers = {"W": 600, "B": 600}
    call_count = {"n": 0}
    real_redo = gc.redo_turn
    def counting(joueur):
        call_count["n"] += 1
        return real_redo(joueur)
    monkeypatch.setattr(gc, "redo_turn", counting)
    inputs = iter(["redo 2", "quit"])
    monkeypatch.setattr(gc, "_get_input_or_network",
                        lambda prompt="", timeout_check=None: next(inputs))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.play_turn()
    # First redo restores W+B (full round, symmetric).
    # Second iteration: redo_history[0] is W (it's now W's turn again
    # after one round restored, since len(history)=2, joueur_actuel
    # flips). The second redo_turn call restores W+B again.
    assert call_count["n"] == 2
    assert len(gc.history) == 4
    assert gc.redo_history == []

def test_undo_invalid_n_does_not_call_annuler(gc, monkeypatch):
    """undo with bad N must reject without invoking undo_turn."""
    p1 = HumanPlayer("Ali", "A", "W")
    p2 = HumanPlayer("Bob", "B", "B")
    gc.players = [p1, p2]
    gc.history = [(Move(0, 1, 2), "W"), (Move(3, 4, 5), "B")]
    gc.timers = {"W": 600, "B": 600}
    call_count = {"n": 0}
    def counting(*a, **kw):
        call_count["n"] += 1
        return True
    monkeypatch.setattr(gc, "undo_turn", counting)
    inputs = iter(["undo abc", "quit"])
    monkeypatch.setattr(gc, "_get_input_or_network",
                        lambda prompt="", timeout_check=None: next(inputs))
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.play_turn()
    assert call_count["n"] == 0
    assert any("Invalid count" in m for m in gc.cli.messages)

# ── network player turn ───────────────────────────────────────────────────────

def test_network_player_turn(gc, monkeypatch):
    p2 = NetworkPlayer("Remote", "B", MagicMock())
    p1 = MagicMock(couleur="W", color_code="W")
    gc.players = [p1, p2]
    gc.history.append((MagicMock(), "W"))
    gc.timers = {"W": 600, "B": 600}
    monkeypatch.setattr(p2, "get_action", lambda board: "d10-d8/d5")
    monkeypatch.setattr(time, "sleep", lambda x: None)
    monkeypatch.setattr(gc, "_get_input_or_network", lambda prompt="", timeout_check=None: "quit")
    monkeypatch.setattr(gc, "prompt_save_before_quit", lambda: True)
    gc.play_turn()
    assert len(gc.history) == 2
