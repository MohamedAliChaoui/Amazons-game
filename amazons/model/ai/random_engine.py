"""Random baseline AI engine.

Selects a uniformly random legal move. Useful as a baseline for
benchmarking and as a fallback engine.
"""

import random


class RandomEngine:
    """Baseline AI that plays random legal moves."""

    def best_move(self, board, color):
        """Pick a random legal move.

        Args:
            board: Current :class:`~amazons.model.board.board.Board`.
            color: ``'W'`` or ``'B'``.

        Returns:
            A random :class:`~amazons.model.board.move.Move`, or
            ``None`` if no legal move exists.
        """
        legal_moves = list(board.get_legal_moves(color))

        if not legal_moves:
            return None

        return random.choice(legal_moves)
