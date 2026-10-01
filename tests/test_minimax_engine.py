import math
from unittest.mock import MagicMock

from amazons.model.ai.minimax_engine import MinimaxEngine


class DummyBoard:
    def __init__(self, legal_moves=None):
        self.legal_moves = legal_moves or {}
        self.played = []
        self.undone = []

    def get_legal_moves(self, color):
        return list(self.legal_moves.get(color, []))

    def play_move(self, move):
        self.played.append(move)

    def undo_move(self, move, color):
        self.undone.append((move, color))


def test_minimax_best_move_returns_none_when_no_legal_moves():
    board = DummyBoard({"W": []})
    engine = MinimaxEngine(depth=2)

    assert engine.best_move(board, "W") is None


def test_minimax_best_move_keeps_first_move_if_time_limit_expires(monkeypatch):
    board = DummyBoard({"W": ["m1", "m2"]})
    engine = MinimaxEngine(depth=2, time_limit=0.5)
    fake_times = iter([0.0, 1.0, 1.1])
    monkeypatch.setattr("amazons.model.ai.minimax_engine.time.time", lambda: next(fake_times))

    assert engine.best_move(board, "W") == "m1"
    assert board.played == []


def test_minimax_best_move_prefers_highest_scoring_move(monkeypatch):
    board = DummyBoard({"W": ["m1", "m2"]})
    engine = MinimaxEngine(depth=2)
    scores = {"m1": 1, "m2": 5}

    monkeypatch.setattr(
        engine,
        "minimax",
        lambda board, depth, alpha, beta, maximizing, color: scores[board.played[-1]],
    )
    monkeypatch.setattr("amazons.model.ai.minimax_engine.time.time", lambda: 0.0)

    assert engine.best_move(board, "W") == "m2"
    assert board.undone == [("m1", "W"), ("m2", "W")]


def test_minimax_returns_evaluator_score_on_depth_zero(monkeypatch):
    engine = MinimaxEngine(depth=2)
    board = DummyBoard()
    monkeypatch.setattr(
        "amazons.model.ai.minimax_engine.Evaluator.evaluate",
        lambda board, color, evaluator: 42,
    )

    assert engine.minimax(board, 0, -math.inf, math.inf, True, "W") == 42


def test_minimax_returns_infinity_when_no_moves():
    engine = MinimaxEngine(depth=2)
    board = DummyBoard({"W": []})

    assert engine.minimax(board, 1, -math.inf, math.inf, True, "W") == -math.inf
    assert engine.minimax(board, 1, -math.inf, math.inf, False, "W") == math.inf


def test_minimax_maximizing_branch_returns_best_value(monkeypatch):
    board = DummyBoard({"W": ["a", "b"]})
    engine = MinimaxEngine(depth=2)
    values = {"a": 7, "b": 3}

    def fake_eval(board, color, evaluator):
        return values[board.played[-1]]

    monkeypatch.setattr("amazons.model.ai.minimax_engine.Evaluator.evaluate", fake_eval)

    result = engine.minimax(board, 1, -math.inf, math.inf, True, "W")

    assert result == 7


def test_minimax_minimizing_branch_prunes(monkeypatch):
    board = DummyBoard({"B": ["a", "b"], "W": ["reply1", "reply2"]})
    engine = MinimaxEngine(depth=2)
    values = {"reply1": -4, "reply2": 10}

    def fake_eval(board, color, evaluator):
        return values[board.played[-1]]

    monkeypatch.setattr("amazons.model.ai.minimax_engine.Evaluator.evaluate", fake_eval)

    result = engine.minimax(board, 1, -3, math.inf, False, "B")

    assert result == -4
    assert board.played.count("reply2") == 0
