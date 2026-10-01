from types import SimpleNamespace
from unittest.mock import MagicMock

from amazons import __main__ as entrypoint
from amazons.model.ai.iterative_deepening import IterativeDeepening
from amazons.model.ai.mcts_engine import MCTSEngine
from amazons.model.ai.minimax_engine import MinimaxEngine
from amazons.model.ai.random_engine import RandomEngine
from amazons.model.board.move import Move


def test_load_config_parses_typed_defaults(tmp_path, monkeypatch):
    config_path = tmp_path / "amazonsrc"
    config_path.write_text(
        "[defaults]\n"
        "size = 8\n"
        "time = 12.5\n"
        "ai_time = 2.5\n"
        "ai_mode = iterative\n"
        "ai_minimax_scoring = mobility\n"
        "ai_mcts_selection = UCT\n"
        "verbose = true\n"
        "debug = false\n"
        "blitz = true\n"
        "gui = false\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(entrypoint, "CONFIG_FILE", config_path)

    defaults = entrypoint.load_config()

    assert defaults == {
        "size": 8,
        "time": 12.5,
        "ai_time": 2.5,
        "ai_mode": "iterative",
        "ai_minimax_scoring": "mobility",
        "ai_mcts_selection": "UCT",
        "verbose": True,
        "debug": False,
        "blitz": True,
        "gui": False,
    }


def test_validate_args_rejects_invalid_size(capsys):
    args = SimpleNamespace(size=3, time=entrypoint.DEFAULT_TIME_LIMIT, blitz=False)

    assert entrypoint.validate_args(args) is False
    assert "size must be between" in capsys.readouterr().err


def test_validate_args_warns_when_time_without_blitz(capsys):
    args = SimpleNamespace(size=6, time=7.5, blitz=False)

    assert entrypoint.validate_args(args) is True
    assert "--blitz" in capsys.readouterr().err


def test_build_ai_engine_matches_requested_mode():
    base_args = {
        "ai_time": 1.5,
        "ai_minimax_depth": 4,
        "ai_minimax_scoring": "hybrid",
    }

    assert isinstance(
        entrypoint.build_ai_engine(
            SimpleNamespace(ai_mode="random", **base_args)
        ),
        RandomEngine,
    )
    assert isinstance(
        entrypoint.build_ai_engine(
            SimpleNamespace(ai_mode="mcts", **base_args)
        ),
        MCTSEngine,
    )
    assert isinstance(
        entrypoint.build_ai_engine(
            SimpleNamespace(ai_mode="iterative", **base_args)
        ),
        IterativeDeepening,
    )
    assert isinstance(
        entrypoint.build_ai_engine(
            SimpleNamespace(ai_mode="minimax", **base_args)
        ),
        MinimaxEngine,
    )


def test_format_move_returns_algebraic_triplet():
    move = Move(
        Move.from_algebraic("a1", 6),
        Move.from_algebraic("a2", 6),
        Move.from_algebraic("b2", 6),
    )

    assert entrypoint.format_move(move, 6) == "a1-a2/b2"


def test_load_saved_game_marks_controller_loaded(monkeypatch, capsys):
    controller = MagicMock()
    controller.is_loaded_from_save = False
    monkeypatch.setattr(
        entrypoint.SaveLoadManager,
        "load_game",
        lambda controller, filepath: (True, "Loaded"),
    )

    assert entrypoint.load_saved_game(controller, "save.amz") is True
    assert controller.is_loaded_from_save is True
    assert capsys.readouterr().out.strip() == "Loaded"
