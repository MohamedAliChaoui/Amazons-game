from amazons.controller.engine.game_controller import GameController
from amazons.model.players.ai_player import AIPlayer


def test_ai_vs_ai_minimax_hybrid_vs_mcts():
    """Runs a full headless game between two AIs
    to exercise the engine core."""
    gc = GameController(size=6)
    gc.timers = {"W": 100.0, "B": 100.0}
    gc.ai_time = 0.05

    gc.players = [
        AIPlayer(
            "AI_Minimax",
            "W",
            ai_mode="minimax",
            ai_depth=1,
            ai_evaluator="hybrid",
        ),
        AIPlayer("AI_MCTS", "B", ai_mode="mcts"),
    ]

    original_end = gc.handle_end_game
    game_over_reason = []

    def mock_end(reason, loser_color=None):
        game_over_reason.append(reason)
        original_end(reason, loser_color)

    gc.handle_end_game = mock_end

    # Start the simulation loop
    try:
        gc.play_turn()
    except StopIteration:
        pass  # Sometimes tests abort depending on CLI logic.

    assert (
        len(game_over_reason) > 0
    ), "Game did not reach Game Over state logically."
    assert (
        len(gc.history) > 2
    ), "Game ended too quickly, probably an initialization fault."


def test_ai_vs_ai_random_vs_minimax_territory():
    """Runs a second game with different AI parameters."""
    gc = GameController(size=4)  # Smaller board ends faster
    gc.timers = {"W": 100.0, "B": 100.0}
    gc.ai_time = 0.05

    gc.players = [
        AIPlayer("AI_Random", "W", ai_mode="random"),
        AIPlayer(
            "AI_Minimax_Terr",
            "B",
            ai_mode="minimax",
            ai_depth=1,
            ai_evaluator="territory",
        ),
    ]

    game_over_reason = []
    orig = gc.handle_end_game
    gc.handle_end_game = lambda r, lc=None: [
        game_over_reason.append(r),
        orig(r, lc),
    ]

    gc.play_turn()
    assert len(game_over_reason) > 0
