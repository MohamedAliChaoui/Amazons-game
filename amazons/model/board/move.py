"""Move representation for the Game of Amazons.

This module defines the Move class which encapsulates a single move
consisting of a queen displacement and an arrow shot.
"""


class Move:
    """Represents a complete move in the Game of Amazons.

    A move consists of three positions: the starting position of the queen,
    the ending position of the queen, and the position where the arrow
    is shot after the queen moves.

    Attributes:
        start_pos: Bitboard index of the queen's starting square.
        end_pos: Bitboard index of the queen's destination square.
        arrow_pos: Bitboard index of the arrow's landing square.
    """

    def __init__(self, start_pos, end_pos, arrow_pos):
        """Initialize a Move.

        Args:
            start_pos: Bitboard index of the queen's starting square.
            end_pos: Bitboard index of the queen's destination square.
            arrow_pos: Bitboard index of the arrow's landing square.
        """
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.arrow_pos = arrow_pos

    @staticmethod
    def from_algebraic(coord, size):
        """Convert algebraic notation to a bitboard index.

        The coordinate 'a1' refers to the bottom-left corner of the board.

        Args:
            coord: Algebraic coordinate string (e.g. ``'a1'``, ``'e10'``).
            size: Board dimension (number of rows/columns).

        Returns:
            The bitboard index corresponding to *coord*.

        Raises:
            ValueError: If the coordinate string is malformed.
        """
        coord = coord.lower().strip()
        if len(coord) < 2:
            raise ValueError(f"Coordinate {coord!r} is too short")
        if not coord[0].isalpha():
            raise ValueError(f"Coordinate {coord!r} has invalid column letter")
        if not coord[1:].isdigit():
            raise ValueError(f"Coordinate {coord!r} has invalid row number")

        col = ord(coord[0]) - ord("a")
        row_num = int(coord[1:])
        row = size - row_num

        if not (0 <= col < size) or not (0 <= row < size):
            raise ValueError(f"Coordinate {coord!r} out of bounds for a {size}x{size} board")

        return row * size + col

    @staticmethod
    def to_algebraic(pos, size):
        """Convert a bitboard index to algebraic notation.

        Args:
            pos: Bitboard index.
            size: Board dimension.

        Returns:
            Algebraic coordinate string (e.g. ``'a1'``).
        """
        if not (0 <= pos < size * size):
            raise ValueError(f"Position {pos} out of bounds for a {size}x{size} board")
        row = pos // size
        col = pos % size
        letter = chr(ord("a") + col)
        number = size - row
        return f"{letter}{number}"

    def __str__(self):
        return (
            f"Move({self.start_pos} -> {self.end_pos}, arrow {self.arrow_pos})"
        )

    def __eq__(self, other):
        if not isinstance(other, Move):
            return False
        return (
            self.start_pos == other.start_pos
            and self.end_pos == other.end_pos
            and self.arrow_pos == other.arrow_pos
        )
