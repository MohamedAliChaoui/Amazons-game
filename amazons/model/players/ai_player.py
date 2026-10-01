"""AI player for the Game of Amazons.

This module provides :class:`AIPlayer`, an artificial player that
delegates move computation to one of the available search engines
(random, minimax, iterative deepening, or MCTS).
"""

from amazons.model.ai.random_engine import RandomEngine
from amazons.model.ai.minimax_engine import MinimaxEngine
from amazons.model.ai.iterative_deepening import IterativeDeepening
from amazons.model.ai.mcts_engine import MCTSEngine
from amazons.model.players.player import Player


DEFAULT_AI_TIME_LIMIT = 5
AI_MODE_MINIMAX = "minimax"
AI_MODE_ITERATIVE = "iterative"
AI_MODE_MCTS = "mcts"


class AIPlayer(Player):
    """An artificial player controlled by a search engine.

    Attributes:
        ai_mode: Search algorithm identifier
            (``'random'``, ``'minimax'``, ``'iterative'``, ``'mcts'``).
        ai_depth: Maximum search depth for minimax.
        ai_evaluator: Evaluation function name
            (``'hybrid'``, ``'territory'``, ``'mobility'``).
    """

    def __init__(  # pylint: disable=too-many-arguments
        self, nom, couleur, ai_mode="random", ai_depth=2, ai_evaluator="hybrid"
    ):
        """Initialize an AI player.

        Args:
            nom: Display name for the bot.
            couleur: ``'W'`` or ``'B'``.
            ai_mode: Search algorithm to use.
            ai_depth: Search depth limit for minimax.
            ai_evaluator: Board evaluation function.
        """
        super().__init__(nom, couleur)

        self.ai_mode = ai_mode
        self.ai_depth = ai_depth
        self.ai_evaluator = ai_evaluator

    def _build_engine(self, time_limit):
        """Return the configured search engine instance."""
        if self.ai_mode == AI_MODE_MINIMAX:
            return MinimaxEngine(
                depth=self.ai_depth,
                evaluator=self.ai_evaluator,
                time_limit=time_limit,
            )
        if self.ai_mode == AI_MODE_ITERATIVE:
            return IterativeDeepening(
                evaluator=self.ai_evaluator,
                time_limit=time_limit or DEFAULT_AI_TIME_LIMIT,
            )
        if self.ai_mode == AI_MODE_MCTS:
            return MCTSEngine(time_limit=time_limit or DEFAULT_AI_TIME_LIMIT)
        return RandomEngine()

    def get_action(  # pylint: disable=missing-type-doc
        self, board, time_limit=None
    ):
        """Compute the best move using the configured engine.

        Args:
            board: Current :class:`~amazons.model.board.board.Board`.
            time_limit: Time budget in seconds (passed to the engine).

        Returns:
            A :class:`~amazons.model.board.move.Move`, or ``None``
            if no legal move exists.
        """
        engine = self._build_engine(time_limit)
        return engine.best_move(board, self.color_code)
