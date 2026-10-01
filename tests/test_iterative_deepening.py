from unittest.mock import MagicMock

from amazons.model.ai.iterative_deepening import IterativeDeepening


def test_iterative_deepening_keeps_latest_non_none_move(monkeypatch):
    moves = iter([None, "move-depth-2"])
    created = []

    class DummyMinimax:
        def __init__(self, depth, evaluator, time_limit):
            created.append((depth, evaluator, time_limit))

        def best_move(self, board, color):
            return next(moves)

    fake_times = iter([0.0, 0.1, 0.2, 0.3, 0.4, 1.2])
    monkeypatch.setattr("amazons.model.ai.iterative_deepening.MinimaxEngine", DummyMinimax)
    monkeypatch.setattr("amazons.model.ai.iterative_deepening.time.time", lambda: next(fake_times))

    engine = IterativeDeepening(time_limit=1.0, evaluator="mobility")

    assert engine.best_move(board=MagicMock(), color="W") == "move-depth-2"
    assert created[0][0] == 1
    assert created[1][0] == 2
    assert all(item[1] == "mobility" for item in created)


def test_iterative_deepening_returns_none_if_time_limit_already_elapsed(monkeypatch):
    called = []

    class DummyMinimax:
        def __init__(self, *args, **kwargs):
            called.append(True)

        def best_move(self, board, color):
            return "unexpected"

    fake_times = iter([0.0, 10.0])
    monkeypatch.setattr("amazons.model.ai.iterative_deepening.MinimaxEngine", DummyMinimax)
    monkeypatch.setattr("amazons.model.ai.iterative_deepening.time.time", lambda: next(fake_times))

    engine = IterativeDeepening(time_limit=1.0)

    assert engine.best_move(board=MagicMock(), color="B") is None
    assert called == []
