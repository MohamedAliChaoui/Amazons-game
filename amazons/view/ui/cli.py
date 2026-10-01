"""Command-line interface view for the Game of Amazons (F4, F15).

Provides the :class:`ViewCli` class that handles all text-based user
interaction: welcome screen, board display, help text, move history,
and input prompts.  Tab-completion of commands is enabled via
``readline`` when available.
"""

import builtins
import sys


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    return getattr(builtins, "_", lambda s: s)(message)


try:
    import readline
except ImportError:
    readline = None


COMMANDS = [
    "new",
    "new P1",
    "show board",
    "show history",
    "show time",
    "show configuration",
    "history",
    "hist",
    "server list",
    "server start",
    "server stop",
    "server status",
    "players",
    "players P1",
    "scoreboard",
    "join",
    "ping",
    "status",
    "move",
    "choice",
    "undo",
    "redo",
    "help",
    "quit",
    "load",
    "save",
    "pause",
    "resume",
    "hint",
    "set",
    "accept",
    "decline",
    "cancel",
]


if readline:

    def completer(text, state):
        """Return the next matching command for tab-completion."""
        options = [command for command in COMMANDS if command.startswith(text)]
        if state < len(options):
            return options[state]
        return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")


class ViewCli:
    """Text-mode view for the Game of Amazons.

    All display and input methods used by the
    :class:`~amazons.controller.engine.game_controller.GameController`
    are defined here.
    """

    def welcome(self, size: int) -> None:
        """Display the welcome banner.

        Args:
            size: Default board size shown to the user.
        """
        print(_("=== AMAZONS CLI ==="))
        print(_("Board size Default: {size}").format(size=size))
        print(_("Type 'help' or 'h' to see commands."))
        print(_("Startup options are available with: " "python -m amazons -h"))
        print(_("Type 'show configuration' to inspect the active settings."))

    def prompt(self):
        """Read a command from standard input.

        Returns:
            The user input stripped and lowercased.
        """
        return input(">> ").strip().lower()

    def msg(self, text):
        """Print a message to the user.

        Args:
            text: Message string to display.
        """
        print(text)

    def error(self, text):
        """Print an error message to stderr.

        Args:
            text: Error message string to display.
        """
        print(text, file=sys.stderr)

    def ask_board_size(self):
        """Prompt the user for a board size between 4 and 11.

        Returns:
            A valid board size integer.
        """
        while True:
            try:
                size = int(input(_("Board size (4-11): ")))
                if 4 <= size <= 11:
                    return size
                print(_("Size must be between 4 and 11."))
            except ValueError:
                print(_("Enter a valid number."))

    def show_help(self):
        """Display the list of available commands and startup options."""
        print(_("""Commands:
            new | n [hu|ai|aiai|network]  Start a new game
            new PLAYER_ID                Invite an idle player to a new game
            show board | sb              Display the board
            show history                 Display move history
            history | hist               Show move history
            show time                    Display remaining time
            show configuration           Display current settings
            server list                  Discover servers on LAN
            server start [port]          Start the local server
            server stop                  Stop the local server
            server status                Show server port, clients and games
            players [PLAYER_ID]          Show connected players or one profile
            scoreboard                   Show player wins, losses and games
            join <host[:port]>           Connect to a remote server
            ping                         Ping the connected server
            status                       Show network status
            move <from>-<to>             Start a move; arrow is prompted
                                         separately
            choice <square>              Show legal moves from a square
            undo [N]                     Undo the last round; with N, repeat
                                         undo up to N times (consent is asked
                                         each time in human-vs-human)
            redo [N]                     Redo the last undone round; with N,
                                         repeat redo up to N times (may stop
                                         early if the next redo is not yours)
            accept                       Accept the current invitation
            decline                      Decline the current invitation
            cancel                       Cancel the pending invitation
            help | h                     Show help
            quit | q                     Exit

            Startup options:
                python -m amazons -h
                -n, --size
                -t, --time
                -g, --gui
                --ai-time
                --ai-mode
                --ai-minimax-scoring
                --ai-minimax-depth
            """))

    def show_history(self, history, size):
        """Display the move history in algebraic notation.

        Args:
            history: List of ``(Move, color)`` tuples.
            size: Board dimension (needed for coordinate conversion).
        """
        if not history:
            print(_("History is empty."))
            return

        print(_("\nMove History:"))
        from amazons.model.board.move import Move

        for index, (move, color) in enumerate(history, 1):
            start = Move.to_algebraic(move.start_pos, size)
            end = Move.to_algebraic(move.end_pos, size)
            arrow = Move.to_algebraic(move.arrow_pos, size)
            print(f"{index}. {color}: {start}-{end}/{arrow}")

    def show_board(self, array_board):
        """Render the board to the terminal with coordinates.

        Args:
            array_board: 2-D list from
                :meth:`~amazons.model.board.board.Board.get_board_array`.
        """
        grid = array_board
        size = len(grid)

        print(_("\nBoard:"))
        letters = " ".join(chr(ord("a") + i) for i in range(size))
        print("     " + letters)

        for row_index, row in enumerate(grid):
            display_row_num = size - row_index
            prefix = f"{display_row_num:<2} |"
            print(f"{prefix} " + " ".join(row))

    def show_board_possible_moves(self, array_board, highlights=None):
        """Render the board with highlighted legal-move squares.

        Squares where the selected queen can move or shoot are shown
        as ``*`` instead of ``.``.

        Args:
            array_board: 2-D board array.
            highlights: List of ``(row, col)`` tuples to highlight.
        """
        grid = array_board
        if highlights:
            for row, col in highlights:
                if 0 <= row < len(grid) and 0 <= col < len(grid[0]):
                    if grid[row][col] == ".":
                        grid[row][col] = "*"
        self.show_board(grid)

    def ask_opponent_type(self):
        """Prompt the user for an opponent mode.

        Returns:
            One of ``'hu'``, ``'ai'``, ``'aiai'``, or ``'network'``.
        """
        while True:
            choice = (
                input(_("Choose opponent mode (hu/ai/aiai/network): "))
                .strip()
                .lower()
            )
            if choice in ("hu", "human"):
                return "hu"
            if choice == "ai":
                return "ai"
            if choice == "aiai":
                return "aiai"
            if choice == "network":
                return "network"
            print(
                _("Invalid input, please choose 'hu', 'ai', 'aiai' or 'network'.")
            )

    def input_cli(self, msg):
        """Read a line of input with a custom prompt.

        Args:
            msg: Prompt string to display.

        Returns:
            The raw user input string.
        """
        return input(msg)


# Backward compatibility for older imports that still use
# ``from ...cli import View_Cli``.
View_Cli = ViewCli
