"""Iterative deepening minimax search (F34).

This module wraps :class:`~amazons.model.ai.minimax_engine.MinimaxEngine`
with iterative deepening so that the best move found so far is always
available when the time budget runs out.
"""

import time
from amazons.model.ai.minimax_engine import MinimaxEngine


class IterativeDeepening:
    """Minimax with iterative deepening.

    The algorithm runs successive minimax searches at increasing depths
    until the time budget is exhausted, keeping the best move found so
    far at each depth.

    Attributes:
        time_limit: Maximum thinking time in seconds.
        evaluator: Evaluation function name passed to minimax.
    """

    def __init__(self, time_limit=5, evaluator="territory"):
        """Initialize the iterative deepening engine.

        Args:
            time_limit: Time budget in seconds.
            evaluator: Evaluation function name.
        """
        self.time_limit = time_limit
        self.evaluator = evaluator

    def best_move(self, board, color):
        """Find the best move by progressively deepening the search.

        Args:
            board: Current :class:`~amazons.model.board.board.Board`.
            color: ``'W'`` or ``'B'``.

        Returns:
            The best :class:`~amazons.model.board.move.Move` found
            within the time budget, or ``None``.
        """
        start_time = time.time()

        depth = 1
        best_move = None

        while True:

            if time.time() - start_time > self.time_limit:
                break

            remaining = self.time_limit - (time.time() - start_time)
            minimax = MinimaxEngine(
                depth=depth,
                evaluator=self.evaluator,
                time_limit=remaining,
            )

            move = minimax.best_move(board, color)

            if move is not None:
                best_move = move

            depth += 1

        return best_move
