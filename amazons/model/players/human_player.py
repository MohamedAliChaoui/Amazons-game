"""Human player for the Game of Amazons.

This module defines the :class:`HumanPlayer` whose moves are entered
interactively through the CLI or GUI.
"""

from amazons.model.players.player import Player


class HumanPlayer(Player):
    """A human player whose moves are handled by the controller.

    Attributes:
        prenom: First name (optional).
        score: Accumulated score across games.
    """

    def __init__(self, nom, prenom, couleur):
        """Initialize a human player.

        Args:
            nom: Last name / display name.
            prenom: First name.
            couleur: ``'W'`` or ``'B'``.
        """
        super().__init__(nom, couleur)
        self.player_id = id(self)
        self.prenom = prenom
        self.score = 0

    def get_action(self, board, time_limit=None):
        """No-op: human moves are handled interactively by the controller."""
        return None

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.color_name})"


# Backward compatibility for older imports that still use
# ``from ...human_player import human_player``.
# pylint: disable=invalid-name
human_player = HumanPlayer
