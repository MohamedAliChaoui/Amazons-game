"""Bitboard-based board representation for the Game of Amazons.

This module implements the game board using bitboards (integers used as
bit arrays) so that move generation, validation, and territory scoring
can be performed efficiently with bitwise operations (F26, F27).
"""

from amazons.model.board.move import Move


class Board:
    """Game board represented by three bitboards.

    Each bitboard is a Python integer where bit *i* is set when the
    corresponding square is occupied by that piece type.  Squares are
    numbered row-major from the top-left corner (index 0) to the
    bottom-right corner (index ``size*size - 1``).

    Attributes:
        size: Side length of the square board.
        white_bb: Bitboard for white queens.
        black_bb: Bitboard for black queens.
        arrow_bb: Bitboard for arrows (blocked squares).
    """

    def __init__(self, size):
        """Create a new board and place queens in their initial positions.

        Args:
            size: Side length of the board (4–11).
        """
        self.size = size
        self.white_bb = 0
        self.black_bb = 0
        self.arrow_bb = 0
        self.init_board()

    def copy(self):
        """Return a deep copy of this board.

        Returns:
            A new ``Board`` instance with identical bitboards.
        """
        new_board = Board(self.size)

        new_board.white_bb = self.white_bb
        new_board.black_bb = self.black_bb
        new_board.arrow_bb = self.arrow_bb

        return new_board

    def init_board(self):
        """Place queens in their default starting positions.

        The layout adapts to the board size:
        * ``size == 4``: 2 queens per side.
        * ``size == 5``: 3 queens per side.
        * ``size >= 6``: 4 queens per side (standard).
        """
        n = self.size
        self.white_bb = 0
        self.black_bb = 0
        self.arrow_bb = 0

        if n == 4:
            whites = [(0, 0), (0, n - 1)]

        elif n == 5:
            middle_row = n // 2
            offset = max(1, n // 4)

            whites = [
                (0, middle_row - offset),
                (0, middle_row + offset),
                (offset, middle_row),
            ]

        else:
            third = n // 3
            whites = [
                (third, 0),
                (third, n - 1),
                (0, third),
                (0, n - 1 - third),
            ]

        for row, col in whites:
            pos_white = row * n + col
            pos_black = (n - 1 - row) * n + (n - 1 - col)

            self.white_bb |= 1 << pos_white
            self.black_bb |= 1 << pos_black

    def occupied(self):
        """Return a bitboard of all occupied squares."""
        return self.white_bb | self.black_bb | self.arrow_bb

    def get_board_array(self):
        """Build a 2-D list used for display purposes.

        Returns:
            A list of lists where each cell is one of
            ``'W'`` (white queen), ``'B'`` (black queen),
            ``'X'`` (arrow) or ``'.'`` (empty).
        """
        board_array = []
        for row in range(self.size):
            line = []
            for col in range(self.size):
                pos = row * self.size + col
                if self.white_bb & (1 << pos):
                    line.append("W")
                elif self.black_bb & (1 << pos):
                    line.append("B")
                elif self.arrow_bb & (1 << pos):
                    line.append("X")
                else:
                    line.append(".")
            board_array.append(line)
        return board_array

    def get_queen_moves_iterator(self, start_pos, occupied_bb):
        """Yield all squares reachable from *start_pos* by sliding like a queen.

        The iterator stops in each direction when it hits an occupied
        square or the edge of the board.

        Args:
            start_pos: Bitboard index of the starting square.
            occupied_bb: Bitboard of all occupied squares.

        Yields:
            Bitboard indices of reachable squares.
        """
        row_start = start_pos // self.size
        col_start = start_pos % self.size

        directions = [
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ]

        for dr, dc in directions:
            row = row_start
            col = col_start
            while True:
                row += dr
                col += dc

                if not (0 <= row < self.size and 0 <= col < self.size):
                    break

                pos = row * self.size + col
                if occupied_bb & (1 << pos):
                    break

                yield pos

    def get_legal_moves(self, color):
        """Generate all legal moves for the given color.

        A legal move consists of moving a queen to an empty square
        reachable by sliding, then shooting an arrow from the queen's
        new position to another reachable empty square.

        Args:
            color: ``'W'`` for white or ``'B'`` for black.

        Yields:
            :class:`Move` objects representing each legal move.
        """
        my_bb = self.white_bb if color == "W" else self.black_bb
        occupied = self.occupied()

        temp_bb = my_bb
        while temp_bb:
            lsb = temp_bb & -temp_bb
            start_pos = lsb.bit_length() - 1
            temp_bb &= temp_bb - 1

            for end_pos in self.get_queen_moves_iterator(
                start_pos, occupied
            ):
                mask_start = 1 << start_pos
                mask_end = 1 << end_pos
                occupied_after_move = (
                    occupied & ~mask_start
                ) | mask_end

                for arrow_pos in self.get_queen_moves_iterator(
                    end_pos, occupied_after_move
                ):
                    yield Move(start_pos, end_pos, arrow_pos)

    def has_moves(self, color):
        """Check whether the player has at least one legal move.

        This is faster than generating all moves because it returns
        as soon as the first reachable square is found.

        Args:
            color: ``'W'`` or ``'B'``.

        Returns:
            ``True`` if the player can still move, ``False`` otherwise.
        """
        my_bb = self.white_bb if color == "W" else self.black_bb

        occupied = self.occupied()

        temp_bb = my_bb
        while temp_bb:
            lsb = temp_bb & -temp_bb
            pos = lsb.bit_length() - 1
            temp_bb &= temp_bb - 1
            moves = self.get_queen_moves_iterator(pos, occupied)
            try:
                next(moves)
                return True
            except StopIteration:
                continue

        return False

    def is_valid_queen_move(self, start_pos, end_pos, color):
        """Validate a queen displacement.

        Args:
            start_pos: Bitboard index of the queen's current position.
            end_pos: Bitboard index of the intended destination.
            color: ``'W'`` or ``'B'``.

        Returns:
            ``True`` if the move is legal, or an error message string
            explaining why it is not.
        """
        if color == "W":
            if not (self.white_bb & (1 << start_pos)):
                return "Start position invalid. It's not your queen (White)."
        else:
            if not (self.black_bb & (1 << start_pos)):
                return "Start position invalid. It's not your queen (Black)."

        occupied = self.occupied()
        for pos in self.get_queen_moves_iterator(start_pos, occupied):
            if pos == end_pos:
                return True
        return "Queen movement invalid (blocked or non-orthogonal/diagonal)."

    def is_valid_arrow_shot(self, start_pos, arrow_pos):
        """Validate an arrow shot from *start_pos* to *arrow_pos*.

        Args:
            start_pos: Bitboard index from which the arrow is shot.
            arrow_pos: Bitboard index of the intended arrow landing.

        Returns:
            ``True`` if valid, or an error message string.
        """
        occupied = self.occupied()
        for pos in self.get_queen_moves_iterator(start_pos, occupied):
            if pos == arrow_pos:
                return True
        return "Arrow shot invalid (blocked or non-orthogonal/diagonal)."

    def is_valid_move(self, move, color):
        """Validate a complete move (queen displacement + arrow shot).

        Args:
            move: A :class:`Move` instance.
            color: ``'W'`` or ``'B'``.

        Returns:
            ``True`` if the full move is legal, or an error message string.
        """
        valid_queen = self.is_valid_queen_move(
            move.start_pos,
            move.end_pos,
            color,
        )
        if valid_queen is not True:
            return valid_queen

        occupied_after_move = (self.occupied() ^ (1 << move.start_pos)) | (
            1 << move.end_pos
        )

        for pos in self.get_queen_moves_iterator(
            move.end_pos, occupied_after_move
        ):
            if pos == move.arrow_pos:
                return True
        return "Arrow shot invalid (blocked or non-orthogonal/diagonal)."

    def move_queen(self, start_pos, end_pos, color):
        """Move a queen without placing an arrow.

        Args:
            start_pos: Current bitboard index of the queen.
            end_pos: Destination bitboard index.
            color: ``'W'`` or ``'B'``.
        """
        if color == "W":
            self.white_bb ^= 1 << start_pos
            self.white_bb |= 1 << end_pos
        else:
            self.black_bb ^= 1 << start_pos
            self.black_bb |= 1 << end_pos

    def place_arrow(self, arrow_pos):
        """Place an arrow on the board.

        Args:
            arrow_pos: Bitboard index of the square to block.
        """
        self.arrow_bb |= 1 << arrow_pos

    def make_move(self, move, color):
        """Apply a full move (queen displacement + arrow shot).

        Args:
            move: A :class:`Move` instance.
            color: ``'W'`` or ``'B'``.
        """
        self.move_queen(move.start_pos, move.end_pos, color)
        self.place_arrow(move.arrow_pos)

    def play_move(self, move):
        """Apply a move, auto-detecting the color from the board state.

        Args:
            move: A :class:`Move` instance.
        """
        if (self.white_bb >> move.start_pos) & 1:
            color = "W"
        elif (self.black_bb >> move.start_pos) & 1:
            color = "B"
        else:
            raise ValueError(f"Attempted to play move from {move.start_pos} which has no queen!")

        self.make_move(move, color)

    def undo_move(self, move, color):
        """Reverse a previously applied move.

        Args:
            move: The :class:`Move` to undo.
            color: ``'W'`` or ``'B'``.
        """
        self.arrow_bb &= ~(1 << move.arrow_pos)
        if color == "W":
            self.white_bb &= ~(1 << move.end_pos)
            self.white_bb |= 1 << move.start_pos
        else:
            self.black_bb &= ~(1 << move.end_pos)
            self.black_bb |= 1 << move.start_pos

    def calculate_territory_scores(self):
        """Compute each player's territory using flood-fill propagation.

        Territory is defined as the set of empty squares reachable by
        each side's queens through adjacent (king-move) steps without
        crossing occupied squares.

        Returns:
            A tuple ``(white_score, black_score)`` counting the number
            of empty squares exclusively reachable by each side.
        """
        occupied = self.occupied()
        size_sq = self.size * self.size

        def get_reachable_territory(queens_bb):
            """Return a bitmask of empty squares reachable by one side."""
            reachable = 0
            frontier = queens_bb

            while frontier:
                reachable |= frontier
                new_frontier = 0

                temp_frontier = frontier
                while temp_frontier:
                    lsb = temp_frontier & -temp_frontier
                    pos = lsb.bit_length() - 1
                    temp_frontier &= temp_frontier - 1
                    row = pos // self.size
                    col = pos % self.size
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue

                            next_row = row + dr
                            next_col = col + dc
                            if (
                                0 <= next_row < self.size
                                and 0 <= next_col < self.size
                            ):
                                next_pos = (
                                    next_row * self.size + next_col
                                )
                                if not (
                                    occupied & (1 << next_pos)
                                ) and not (
                                    reachable & (1 << next_pos)
                                ):
                                    new_frontier |= 1 << next_pos

                frontier = new_frontier

            return reachable & ~queens_bb

        white_territory = get_reachable_territory(self.white_bb)
        black_territory = get_reachable_territory(self.black_bb)

        score_white = white_territory.bit_count()
        score_black = black_territory.bit_count()

        return score_white, score_black
