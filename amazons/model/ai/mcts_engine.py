"""Monte Carlo Tree Search engine with UCT selection (F36).

This module implements the MCTS algorithm using Upper Confidence bounds
applied to Trees (UCT) to select the most promising nodes during the
tree search phase.
"""

import math
import random
import time


class MCTSNode:
    """A node in the MCTS search tree.

    Attributes:
        board: Board snapshot at this node.
        parent: Parent node (``None`` for the root).
        move: The move that led to this node from its parent.
        color: Color whose turn it is at this node.
        children: List of expanded child nodes.
        visits: Number of times this node has been visited.
        wins: Number of wins propagated through this node.
        untried_moves: Legal moves not yet expanded.
    """

    def __init__(self, board, parent=None, move=None, color=None):
        # On ne stocke pas 'board' pour alléger la RAM (remarque Prof)
        self.parent = parent
        self.move = move
        self.color = color

        self.children = []

        self.visits = 0
        self.wins = 0

        self.untried_moves = list(board.get_legal_moves(color))

    def uct_select_child(self):
        """Select the child with the highest UCT value.

        Returns:
            The child :class:`MCTSNode` with the best exploration /
            exploitation trade-off.
        """
        exploration_weight = 1.41

        # Prof check: Le parent veut maximiser SON win-rate. "child.wins" sont les victoires de l'enfant (l'adversaire).
        return max(
            self.children,
            key=lambda child: ((child.visits - child.wins) / child.visits)
            + exploration_weight * math.sqrt(math.log(self.visits) / child.visits),
        )


class MCTSEngine:
    """Monte Carlo Tree Search engine.

    Attributes:
        time_limit: Maximum thinking time in seconds.
    """

    def __init__(self, time_limit=5, selection="UCT"):
        """Initialize the MCTS engine.

        Args:
            time_limit: Time budget in seconds for the search.
            selection: Node selection strategy. Only ``'UCT'`` is
                implemented; ``'ML'`` falls back to UCT with a warning.
        """
        self.time_limit = time_limit
        if selection != "UCT":
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "MCTS selection '%s' is not implemented; using UCT.", selection
            )
        self.selection = "UCT"

    def best_move(self, board, color):
        """Find the best move using MCTS.

        Performs repeated selection → expansion → simulation →
        back-propagation cycles until the time budget is exhausted.

        Args:
            board: Current :class:`~amazons.model.board.board.Board`.
            color: ``'W'`` or ``'B'``.

        Returns:
            The most visited :class:`~amazons.model.board.move.Move`.
        """
        root = MCTSNode(board, None, None, color)

        start = time.time()

        while time.time() - start < self.time_limit:

            node = root
            board_copy = board.copy()

            # 1. SELECTION
            while not node.untried_moves and node.children:

                node = node.uct_select_child()
                board_copy.play_move(node.move)

            # 2. EXPANSION
            if node.untried_moves:

                move = node.untried_moves.pop()

                board_copy.play_move(move)

                next_color = "B" if node.color == "W" else "W"

                child = MCTSNode(board_copy, node, move, next_color)

                node.children.append(child)

                node = child

            # 3. SIMULATION (random playout)
            current_color = node.color

            while True:

                moves = list(board_copy.get_legal_moves(current_color))

                if not moves:
                    break

                move = random.choice(moves)

                board_copy.play_move(move)

                current_color = "B" if current_color == "W" else "W"

            winner = "B" if current_color == "W" else "W"

            # 4. BACK-PROPAGATION
            while node is not None:

                node.visits += 1

                if node.color == winner:
                    node.wins += 1

                node = node.parent

        if not root.children:
            return root.untried_moves[0] if root.untried_moves else None

        best_child = max(root.children, key=lambda c: c.visits)

        return best_child.move
