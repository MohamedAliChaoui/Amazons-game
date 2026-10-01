"""Territory-based evaluation function.

Scores a position by comparing the number of empty squares reachable
by each side's queens (flood-fill territory).
"""


class TerritoryEvaluator:
    """Evaluates a position based on controlled territory."""

    @staticmethod
    def evaluate(board, color):
        """Return the territory advantage for *color*.

        Args:
            board: Current board.
            color: ``'W'`` or ``'B'``.

        Returns:
            ``own_territory - opponent_territory``.
        """
        score_w, score_b = board.calculate_territory_scores()

        if color == "W":
            return score_w - score_b
        else:
            return score_b - score_w
