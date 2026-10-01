"""Minimax search engine with alpha-beta pruning (F32).

This module implements the classic minimax algorithm enhanced with
alpha-beta pruning to efficiently evaluate game positions and choose
the best move for the AI player.
"""

import math
import logging
import time

from amazons.model.ai.evaluator import Evaluator
from amazons.model.color import Color

logger = logging.getLogger(__name__)


class MinimaxEngine:
    """Minimax search with alpha-beta pruning.

    Attributes:
        depth: Maximum search depth.
        evaluator: Name of the evaluation function to use.
        time_limit: Maximum computation time in seconds.
        start_time: Timestamp when the search started.
    """

    def __init__(self, depth=2, evaluator="hybrid", time_limit=None):
        """Initialize the minimax engine.

        Args:
            depth: Maximum search depth.
            evaluator: Evaluation function name
                (``'territory'``, ``'mobility'``, ``'hybrid'``).
            time_limit: Time budget in seconds (``None`` for unlimited).
        """
        self.depth = depth
        self.evaluator = evaluator
        self.time_limit = time_limit
        self.start_time = None

    def _time_exceeded(self) -> bool:
        """Return whether the current search exhausted its time budget."""
        return (
            self.time_limit is not None
            and time.time() - self.start_time >= self.time_limit
        )

    def _evaluate(self, board, color):
        """Evaluate *board* from the perspective of *color*."""
        return Evaluator.evaluate(board, color, self.evaluator)

    @staticmethod
    def _opponent_color(color):
        """Return the opponent color code."""
        return Color.B if color == Color.W else Color.W

    def best_move(self, board, color):
        """Find the best move for *color* from the current position.

        Args:
            board: Current :class:`~amazons.model.board.board.Board`.
            color: ``'W'`` or ``'B'``.

        Returns:
            The best :class:`~amazons.model.board.move.Move`, or
            ``None`` if no legal move exists.
        """
        self.start_time = time.time()

        best_score = -math.inf

        moves = list(board.get_legal_moves(color))

        if not moves:
            return None

        best_move = moves[0]

        for move in moves:
            if self._time_exceeded():
                break

            board.play_move(move)

            score = self.minimax(
                board, self.depth - 1, -math.inf, math.inf, False, color
            )

            board.undo_move(move, color)

            if score > best_score:
                best_score = score
                best_move = move

        logger.debug(
            "Minimax [Depth %s] finished in %.3fs. Best score: %s",
            self.depth,
            time.time() - self.start_time,
            best_score,
        )

        return best_move

    def minimax(self, board, depth, alpha, beta, maximizing, my_color):
        """Recursive minimax with alpha-beta pruning.

        Args:
            board: Current board state.
            depth: Remaining search depth.
            alpha: Alpha bound for pruning.
            beta: Beta bound for pruning.
            maximizing: ``True`` if this is a maximizing node.
            my_color: Color of the AI player (for evaluation).

        Returns:
            The evaluation score of the position.
        """
        if self._time_exceeded():
            return self._evaluate(board, my_color)

        if not depth:
            return self._evaluate(board, my_color)

        current_color = (
            my_color if maximizing else self._opponent_color(my_color)
        )

        moves = list(board.get_legal_moves(current_color))

        if not moves:
            return -math.inf if maximizing else math.inf

        if maximizing:
            value = -math.inf
            for move in moves:
                board.play_move(move)
                value = max(
                    value,
                    self.minimax(
                        board, depth - 1, alpha, beta, False, my_color
                    ),
                )
                board.undo_move(move, current_color)
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value

        value = math.inf
        for move in moves:
            board.play_move(move)
            value = min(
                value,
                self.minimax(board, depth - 1, alpha, beta, True, my_color),
            )
            board.undo_move(move, current_color)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value
