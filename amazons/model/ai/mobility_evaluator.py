"""Mobility-based evaluation function.

Scores a position by comparing the number of legal moves available
to each side.
"""


class MobilityEvaluator:
    """Evaluates a position based on move count difference."""

    @staticmethod
    def evaluate(board, color):
        """Return the mobility advantage for *color*.

        Args:
            board: Current board.
            color: ``'W'`` or ``'B'``.

        Returns:
            ``own_moves - opponent_moves``.
        """
        opponent = "B" if color == "W" else "W"

        my_moves = sum(1 for _ in board.get_legal_moves(color))
        opponent_moves = sum(1 for _ in board.get_legal_moves(opponent))

        return my_moves - opponent_moves
