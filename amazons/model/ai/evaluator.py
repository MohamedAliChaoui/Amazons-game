"""Evaluation function dispatcher (F33).

Provides a unified interface to three evaluation functions:
territory, mobility, and a weighted hybrid of both.
"""

from amazons.model.ai.mobility_evaluator import MobilityEvaluator
from amazons.model.ai.territory_evaluator import TerritoryEvaluator

MODE_TERRITORY = "territory"
MODE_MOBILITY = "mobility"
MODE_HYBRID = "hybrid"


class Evaluator:
    """Dispatches evaluation calls to the configured scoring function."""

    @staticmethod
    def supported_modes():
        """Return the supported evaluator mode names."""
        return ("territory", "mobility", "hybrid")

    @staticmethod
    def evaluate(board, color, mode="hybrid"):
        """Evaluate the board from the perspective of *color*.

        :param board: Current
            :class:`~amazons.model.board.board.Board`.
        :type board: Board
        :param color: ``'W'`` or ``'B'``.
        :type color: str
        :param mode: ``'territory'``, ``'mobility'`` or ``'hybrid'``.
        :type mode: str

        :returns: A numerical score (positive = advantage for *color*).
        """
        if mode == MODE_TERRITORY:
            return TerritoryEvaluator.evaluate(board, color)
        if mode == MODE_MOBILITY:
            return MobilityEvaluator.evaluate(board, color)
        if mode == MODE_HYBRID:
            territory_score = TerritoryEvaluator.evaluate(board, color)
            mobility_score = MobilityEvaluator.evaluate(board, color)
            return 0.6 * territory_score + 0.4 * mobility_score
        raise ValueError(f"Unknown evaluator mode: {mode}")
