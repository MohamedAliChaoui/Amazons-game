from types import SimpleNamespace

import pytest

from amazons.controller.engine import display_controller, move_helper_controller
from amazons.model.ai.random_engine import RandomEngine
from amazons.model.board.board import Board
from amazons.model.board.move import Move
from amazons.model.players.ai_player import AIPlayer
from amazons.model.players.human_player import HumanPlayer


class DummyCLI:
    def __init__(self):
        self.messages = []
        self.highlight_calls = []

    def msg(self, text):
        self.messages.append(text)

    def show_board_possible_moves(self, board_array, highlights):
        self.highlight_calls.append((board_array, highlights))


class DummyController:
    def __init__(self, size=6):
        self.size = size
        self.board = Board(size)
        self.cli = DummyCLI()
        self.ai_mode = "minimax"
        self.ai_time = 2.5
        self.ai_depth = 3
        self.ai_evaluator = "hybrid"
        self.time_limit_per_move = 600.0
        self.is_start_party = False
        self.history = []
        self.server = SimpleNamespace(
            get_status=lambda: {
                "port": 12345,
                "connected_clients": 1,
                "parties_in_progress": 0,
                "active_player_id": "P1",
            },
            get_player=lambda player_id: None,
            get_players=lambda: [],
            get_scoreboard=lambda: [],
        )

    def format_move_notation(self, move, color):
        start = Move.to_algebraic(move.start_pos, self.size)
        end = Move.to_algebraic(move.end_pos, self.size)
        arrow = Move.to_algebraic(move.arrow_pos, self.size)
        return f"{color} {start}-{end}/{arrow}"

    def get_time_status_line(self):
        return "Time remaining -> White: 100.0s | Black: 90.0s"


def identity(message):
    return message


def test_handle_hint_command_reports_no_legal_move(monkeypatch):
    controller = DummyController()
    controller.ai_mode = "random"

    monkeypatch.setattr(
        "amazons.model.ai.random_engine.RandomEngine.best_move",
        lambda self, board, color: None,
    )

    move_helper_controller.handle_hint_command(controller, identity, "W")

    assert controller.cli.messages == [
        "Calculating hint... please wait.",
        "No legal move available.",
    ]


def test_handle_hint_command_formats_move_notation(monkeypatch):
    controller = DummyController()
    move = Move(
        Move.from_algebraic("c6", controller.size),
        Move.from_algebraic("c5", controller.size),
        Move.from_algebraic("b5", controller.size),
    )

    monkeypatch.setattr(
        "amazons.model.ai.minimax_engine.MinimaxEngine.best_move",
        lambda self, board, color: move,
    )

    move_helper_controller.handle_hint_command(controller, identity, "W")

    assert controller.cli.messages[-1] == "Hint: The AI suggests W c6-c5/b5"


def test_show_possible_moves_requires_square_argument():
    controller = DummyController()
    joueur = HumanPlayer("Alice", "", "W")

    move_helper_controller.show_possible_moves(
        controller, identity, "choice", joueur
    )

    assert controller.cli.messages[-1] == "Usage: choice <case> (ex: choice d4)"


def test_show_possible_moves_rejects_invalid_coordinates():
    controller = DummyController()
    joueur = HumanPlayer("Alice", "", "W")

    move_helper_controller.show_possible_moves(
        controller, identity, "choice z99", joueur
    )

    assert "Invalid coordinates" in controller.cli.messages[-1]


def test_show_possible_moves_rejects_wrong_piece_color():
    controller = DummyController()
    joueur = HumanPlayer("Alice", "", "W")

    move_helper_controller.show_possible_moves(
        controller, identity, "choice b2", joueur
    )

    assert controller.cli.messages[-1] == "No white piece at b2"


def test_show_possible_moves_displays_highlights_for_valid_piece():
    controller = DummyController()
    joueur = HumanPlayer("Alice", "", "W")

    move_helper_controller.show_possible_moves(
        controller, identity, "choice c6", joueur
    )

    assert controller.cli.messages[-1].startswith("Moves possible from c6: ")
    assert controller.cli.highlight_calls


def test_display_get_history_lines_handles_empty_history():
    controller = DummyController()

    assert display_controller.get_history_lines(controller) == [
        "No moves played yet."
    ]


def test_display_get_history_lines_formats_turns():
    controller = DummyController()
    controller.history = [
        (
            Move(
                Move.from_algebraic("c6", controller.size),
                Move.from_algebraic("c5", controller.size),
                Move.from_algebraic("b5", controller.size),
            ),
            "W",
        ),
        (
            Move(
                Move.from_algebraic("d1", controller.size),
                Move.from_algebraic("d2", controller.size),
                Move.from_algebraic("e2", controller.size),
            ),
            "B",
        ),
    ]

    lines = display_controller.get_history_lines(controller)

    assert lines == ["1. W c6-c5/b5; B d1-d2/e2;"]


def test_display_show_time_before_start_prints_notice(capsys):
    controller = DummyController()

    display_controller.show_time(controller, identity)

    captured = capsys.readouterr()
    assert "The game has not started yet." in captured.out


def test_display_show_players_unknown_and_empty_states():
    controller = DummyController()
    controller.server = SimpleNamespace(
        get_player=lambda player_id: None,
        get_players=lambda: [],
    )

    display_controller.show_players(controller, identity, "P9")
    display_controller.show_players(controller, identity)

    assert controller.cli.messages == [
        "Unknown player ID.",
        "No players connected.",
    ]


def test_display_show_players_and_scoreboard_and_server_status():
    controller = DummyController()
    controller.server = SimpleNamespace(
        get_status=lambda: {
            "port": 12345,
            "connected_clients": 2,
            "parties_in_progress": 1,
            "active_player_id": "P2",
        },
        get_player=lambda player_id: {
            "id": "P2",
            "name": "Remote",
            "status": "idle",
            "address": ("127.0.0.1", 9999),
        },
        get_players=lambda: [
            {
                "id": "P1",
                "name": "RemoteOne",
                "status": "idle",
                "address": ("127.0.0.1", 4444),
            }
        ],
        get_scoreboard=lambda: [
            {"name": "Alice", "wins": 2, "losses": 1, "played": 3}
        ],
    )

    display_controller.show_server_status(controller, identity)
    display_controller.show_players(controller, identity, "P2")
    display_controller.show_players(controller, identity)
    display_controller.show_scoreboard(controller, identity)

    assert any("Listening port: 12345" in msg for msg in controller.cli.messages)
    assert any(
        "Player P2: Remote | idle | 127.0.0.1:9999" in msg
        for msg in controller.cli.messages
    )
    assert any(
        "P1: RemoteOne | idle | 127.0.0.1:4444" in msg
        for msg in controller.cli.messages
    )
    assert any("Alice: 2 win(s), 1 loss(es), 3 game(s)" in msg for msg in controller.cli.messages)


def test_ai_player_iterative_mcts_and_fallback_random(monkeypatch):
    board = object()

    iterative_engine = SimpleNamespace(best_move=lambda _board, _color: "iter")
    mcts_engine = SimpleNamespace(best_move=lambda _board, _color: "mcts")
    random_engine = SimpleNamespace(best_move=lambda _board, _color: "rand")

    monkeypatch.setattr(
        "amazons.model.players.ai_player.IterativeDeepening",
        lambda **kwargs: iterative_engine,
    )
    monkeypatch.setattr(
        "amazons.model.players.ai_player.MCTSEngine",
        lambda **kwargs: mcts_engine,
    )
    monkeypatch.setattr(
        "amazons.model.players.ai_player.RandomEngine",
        lambda: random_engine,
    )

    assert AIPlayer("BotI", "W", ai_mode="iterative").get_action(board, 1.5) == "iter"
    assert AIPlayer("BotM", "W", ai_mode="mcts").get_action(board, 1.5) == "mcts"
    assert AIPlayer("BotX", "W", ai_mode="unknown").get_action(board, 1.5) == "rand"


def test_human_player_and_random_engine_behaviors():
    player = HumanPlayer("Alice", "Doe", "W")

    assert player.get_action(object()) is None
    assert str(player) == "Alice Doe (white)"

    empty_board = SimpleNamespace(get_legal_moves=lambda color: iter(()))
    assert RandomEngine().best_move(empty_board, "W") is None