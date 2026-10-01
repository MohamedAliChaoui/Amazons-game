"""AI utilities for the Amazons project."""


def create_ai_engine(ai_mode, ai_time, depth, evaluator, mcts_selection="UCT"):
    """Factory to instantiate and return the correct AI Engine."""
    if ai_mode == "random":
        from amazons.model.ai.random_engine import RandomEngine

        return RandomEngine()
    if ai_mode == "mcts":
        from amazons.model.ai.mcts_engine import MCTSEngine

        return MCTSEngine(time_limit=ai_time, selection=mcts_selection)
    if ai_mode == "iterative":
        from amazons.model.ai.iterative_deepening import IterativeDeepening

        return IterativeDeepening(evaluator=evaluator, time_limit=ai_time)

    from amazons.model.ai.minimax_engine import MinimaxEngine

    return MinimaxEngine(
        depth=depth,
        evaluator=evaluator,
        time_limit=ai_time,
    )
