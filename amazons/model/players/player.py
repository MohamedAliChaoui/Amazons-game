"""Abstract base player and network player for the Game of Amazons.

This module defines the ``Player`` abstract base class that every
player type must implement, as well as ``NetworkPlayer`` for remote
opponents connected over the network.
"""

from abc import ABC, abstractmethod
import builtins
import time
from amazons.model.color import Color

try:
    import msvcrt
except ImportError:
    msvcrt = None


MOVE_PREFIX = "MOVE "
LOAD_STATE_PREFIX = "LOAD_STATE "
NAME_PREFIX = "NAME "
CLOCK_PREFIX = "CLOCK "
UNDO_PREFIX = "UNDO_REQ"
GAMEOVER_PREFIX = "GAMEOVER "
LOCAL_UNDO_COMMANDS = {"undo", "u"}
QUIT_COMMANDS = {"quit", "q"}
RETURN_CHARS = {"\r", "\n"}
BACKSPACE_CHARS = {"\b"}
NETWORK_POLL_DELAY = 0.1
CLOCK_MESSAGE_PARTS = 3


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    return getattr(builtins, "_", lambda s: s)(message)


class Player(ABC):
    """Abstract base class for all player types.

    Attributes:
        nom: Display name of the player.
        couleur: Color assigned to this player (``'W'`` or ``'B'``).
    """

    def __init__(self, nom, couleur):
        self.nom = nom
        self.couleur = couleur

    @property
    def color_code(self):
        """Return ``'W'`` or ``'B'`` for board operations."""
        return self.couleur

    @property
    def color_name(self):
        """Return ``'white'`` or ``'black'`` for display."""
        return Color.to_name(self.couleur)

    @abstractmethod
    def get_action(  # pylint: disable=missing-type-doc
        self, board, time_limit=None
    ):
        """Determine the next action to play.

        Args:
            board: Current :class:`~amazons.model.board.board.Board` state.
            time_limit: Optional time budget in seconds.

        Returns:
            A :class:`~amazons.model.board.move.Move` or a command string.
        """
        raise NotImplementedError


class NetworkPlayer(Player):
    """A remote player whose moves arrive over the network.

    Attributes:
        network: The network interface (server or client) used to
            receive and send messages.
        on_name_received: Optional callback invoked when a remote
            ``NAME`` message is received.
        on_clock_received: Optional callback invoked when a remote
            ``CLOCK`` message is received.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        nom,
        couleur,
        network_interface,
        on_name_received=None,
        on_clock_received=None,
    ):
        super().__init__(nom, couleur)
        self.network = network_interface
        self.on_name_received = on_name_received
        self.on_clock_received = on_clock_received

    @staticmethod
    def _strip_move_color_prefix(notation):
        """Remove a leading ``W``/``B`` move color prefix if present."""
        if notation and notation[0] in (Color.W, Color.B):
            return notation[1:]
        return notation

    def _handle_remote_name(self, message):
        """Update the remote player's display name."""
        self.nom = message[len(NAME_PREFIX) :].strip()
        if self.on_name_received:
            self.on_name_received(self.nom)

    def _handle_remote_clock(self, message):
        """Forward an incoming remote clock update if well formed."""
        parts = message.split(maxsplit=2)
        if len(parts) == CLOCK_MESSAGE_PARTS and self.on_clock_received:
            self.on_clock_received(parts[1], parts[2])

    def _handle_network_message(self, raw_message):
        """Process one network message and return an actionable result."""
        if not raw_message:
            return None

        message = raw_message.strip()
        message_upper = message.upper()

        exact_actions = {
            "QUIT_GAME": "QUIT_GAME",
            "QUIT": "QUIT",
        }
        if message_upper in exact_actions:
            return exact_actions[message_upper]

        handlers = (
            (
                MOVE_PREFIX,
                lambda msg: self._strip_move_color_prefix(
                    msg[len(MOVE_PREFIX) :].strip()
                ),
            ),
            (LOAD_STATE_PREFIX, lambda msg: msg),
            (NAME_PREFIX, self._handle_remote_name),
            (CLOCK_PREFIX, self._handle_remote_clock),
            (UNDO_PREFIX, lambda msg: msg),
            (GAMEOVER_PREFIX, lambda _msg: "GAMEOVER"),
        )
        for prefix, handler in handlers:
            if message_upper.startswith(prefix):
                return handler(message)
        return None

    @staticmethod
    def _handle_local_line(line):
        """Validate a locally typed command while waiting on the network."""
        normalized = line.strip().lower()
        if normalized in LOCAL_UNDO_COMMANDS:
            return "LOCAL_UNDO"
        if normalized in QUIT_COMMANDS:
            return "QUIT"
        print(
            _(
                "\n[LOCAL] Only 'undo' or 'quit' allowed. "
                "(Buffer: {line})"
            ).format(line=normalized)
        )
        return None

    def _poll_windows_input(self, local_buffer):
        """Return a local command and the updated input buffer."""
        if not msvcrt or not msvcrt.kbhit():
            return None, local_buffer

        try:
            char = msvcrt.getch().decode("ascii", errors="ignore")
        except Exception:  # pylint: disable=broad-exception-caught
            return None, local_buffer

        if char in RETURN_CHARS:
            print()
            return self._handle_local_line(local_buffer), ""

        if char in BACKSPACE_CHARS:
            if local_buffer:
                local_buffer = local_buffer[:-1]
                print("\b \b", end="", flush=True)
            return None, local_buffer

        if char.isprintable():
            local_buffer += char
            print(char, end="", flush=True)

        return None, local_buffer

    def get_action(  # pylint: disable=missing-type-doc,while-used
        self, board, time_limit=None
    ):
        """Wait for a move or control message from the remote peer.

        Also polls for local keyboard input so the user can type
        ``'undo'`` or ``'quit'`` while waiting.

        Args:
            board: Current board state (unused directly).
            time_limit: Optional time budget (unused directly).

        Returns:
            A move notation string (e.g. ``'e2-e4/e6'``), or a
            control string such as ``'QUIT'``, ``'QUIT_GAME'``,
            ``'LOCAL_UNDO'``, ``'UNDO_REQ'``, or ``'GAMEOVER'``.
        """
        print(
            _(
                "Waiting for remote move from {name}... "
                "(Type 'undo' or 'q' to interrupt)"
            ).format(name=self.nom)
        )
        local_buffer = ""
        while True:
            if action := self._handle_network_message(self.network.receive()):
                return action

            action, local_buffer = self._poll_windows_input(local_buffer)
            if action:
                return action

            time.sleep(NETWORK_POLL_DELAY)
