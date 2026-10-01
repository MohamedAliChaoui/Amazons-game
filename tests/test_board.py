import pytest
from amazons.model.board.board import Board
from amazons.model.board.move import Move

# ---- INITIALISATION ----


def test_init_n4():
    b = Board(4)
    assert bin(b.white_bb).count("1") == 2
    assert bin(b.black_bb).count("1") == 2


def test_init_n5():
    b = Board(5)
    assert bin(b.white_bb).count("1") == 3
    assert bin(b.black_bb).count("1") == 3


def test_init_n8():
    b = Board(8)
    assert bin(b.white_bb).count("1") == 4
    assert bin(b.black_bb).count("1") == 4


def test_init_arrow_bb_zero():
    b = Board(10)
    assert b.arrow_bb == 0


# ---- COPY ----


def test_copy_same_state():
    b = Board(8)
    c = b.copy()
    assert c.white_bb == b.white_bb
    assert c.black_bb == b.black_bb
    assert c.arrow_bb == b.arrow_bb
    assert c.size == b.size


def test_copy_independence():
    b = Board(6)
    c = b.copy()
    c.white_bb = 0
    c.arrow_bb = 0xDEAD
    assert b.white_bb != 0
    assert b.arrow_bb == 0


# ---- OCCUPIED ----


def test_occupied_union():
    b = Board(8)
    assert b.occupied() == (b.white_bb | b.black_bb | b.arrow_bb)


def test_occupied_includes_arrows():
    b = Board(6)
    b.arrow_bb = 1 << 20
    assert b.occupied() & (1 << 20) != 0


# ---- GET_BOARD_ARRAY ----


def test_board_array_size():
    b = Board(6)
    grid = b.get_board_array()
    assert len(grid) == 6
    assert len(grid[0]) == 6


def test_board_array_cell_values():
    b = Board(4)
    b.white_bb = 1 << 0   # row 0, col 0 → 'W'
    b.black_bb = 1 << 1   # row 0, col 1 → 'B'
    b.arrow_bb = 1 << 2   # row 0, col 2 → 'X'
    grid = b.get_board_array()
    assert grid[0][0] == "W"
    assert grid[0][1] == "B"
    assert grid[0][2] == "X"
    assert grid[0][3] == "."


# ---- SYMÉTRIE ----


def test_symmetry():
    b = Board(8)
    N = b.size

    for row in range(N):
        for col in range(N):
            pos = row * N + col
            symmetric_pos = (N - 1 - row) * N + (N - 1 - col)

            white_piece = b.white_bb & (1 << pos)
            black_symmetric = b.black_bb & (1 << symmetric_pos)

            if white_piece:
                assert black_symmetric != 0


# ---- GET_QUEEN_MOVES_ITERATOR ----


def _empty_board(size):
    b = Board(size)
    b.white_bb = 0
    b.black_bb = 0
    b.arrow_bb = 0
    return b


def test_queen_moves_from_corner_reaches_edges():
    b = _empty_board(4)
    moves = list(b.get_queen_moves_iterator(0, 0))
    # From top-left (0): right (1,2,3), down (4,8,12), diagonal (5,10,15)
    assert 1 in moves
    assert 4 in moves
    assert 5 in moves
    assert 15 in moves


def test_queen_moves_blocked_stops_before_obstacle():
    b = _empty_board(4)
    occupied = 1 << 1   # blocker one step right of pos 0
    moves = list(b.get_queen_moves_iterator(0, occupied))
    assert 1 not in moves   # blocker itself not reachable
    assert 2 not in moves   # cannot pass through
    assert 3 not in moves
    assert 4 in moves       # downward still clear


def test_queen_moves_from_surrounded_square():
    b = _empty_board(4)
    # surround pos 5 (row 1, col 1) on all 8 sides
    for pos in [0, 1, 2, 4, 6, 8, 9, 10]:
        b.arrow_bb |= 1 << pos
    moves = list(b.get_queen_moves_iterator(5, b.arrow_bb))
    assert moves == []


def test_queen_moves_count_from_center_open_board():
    b = _empty_board(6)
    center = 2 * 6 + 2  # (row 2, col 2)
    moves = list(b.get_queen_moves_iterator(center, 0))
    assert len(moves) > 10   # ample room on an open board


# ---- GET_LEGAL_MOVES ----


def test_get_legal_moves_white_nonempty():
    b = Board(6)
    moves = list(b.get_legal_moves("W"))
    assert len(moves) > 0


def test_get_legal_moves_black_nonempty():
    b = Board(6)
    moves = list(b.get_legal_moves("B"))
    assert len(moves) > 0


def test_get_legal_moves_none_when_queen_blocked():
    b = _empty_board(4)
    b.white_bb = 1 << 5   # queen at (row 1, col 1)
    # fill all 8 neighbours with arrows
    for pos in [0, 1, 2, 4, 6, 8, 9, 10]:
        b.arrow_bb |= 1 << pos
    moves = list(b.get_legal_moves("W"))
    assert moves == []


def test_get_legal_moves_returns_move_objects():
    b = Board(6)
    move = next(b.get_legal_moves("W"))
    assert hasattr(move, "start_pos")
    assert hasattr(move, "end_pos")
    assert hasattr(move, "arrow_pos")


# ---- HAS_MOVES ----


def test_has_moves_true_initial():
    b = Board(6)
    assert b.has_moves("W") is True
    assert b.has_moves("B") is True


def test_has_moves_false_when_blocked():
    b = _empty_board(4)
    b.white_bb = 1 << 5
    for pos in [0, 1, 2, 4, 6, 8, 9, 10]:
        b.arrow_bb |= 1 << pos
    assert b.has_moves("W") is False


def test_has_moves_false_no_queens():
    b = _empty_board(4)
    assert b.has_moves("W") is False


# ---- IS_VALID_QUEEN_MOVE ----


def test_is_valid_queen_move_valid():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    assert b.is_valid_queen_move(0, 1, "W") is True


def test_is_valid_queen_move_wrong_color():
    b = Board(6)
    # pick first black queen and try to move it as white
    black_pos = (b.black_bb & -b.black_bb).bit_length() - 1
    result = b.is_valid_queen_move(black_pos, black_pos - 1, "W")
    assert result is not True
    assert isinstance(result, str)


def test_is_valid_queen_move_blocked():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    b.arrow_bb = 1 << 1   # blocker directly right
    result = b.is_valid_queen_move(0, 2, "W")
    assert result is not True


def test_is_valid_queen_move_black_wrong_square():
    b = _empty_board(4)
    b.black_bb = 1 << 15
    result = b.is_valid_queen_move(0, 1, "B")   # pos 0 has no black queen
    assert result is not True


# ---- IS_VALID_ARROW_SHOT ----


def test_is_valid_arrow_shot_valid():
    b = _empty_board(4)
    assert b.is_valid_arrow_shot(0, 1) is True


def test_is_valid_arrow_shot_blocked():
    b = _empty_board(4)
    b.arrow_bb = 1 << 1
    result = b.is_valid_arrow_shot(0, 2)
    assert result is not True


# ---- IS_VALID_MOVE ----


def test_is_valid_move_first_legal_move():
    b = Board(6)
    move = next(b.get_legal_moves("W"))
    assert b.is_valid_move(move, "W") is True


def test_is_valid_move_invalid_queen_part():
    b = Board(6)
    black_pos = (b.black_bb & -b.black_bb).bit_length() - 1
    m = Move(black_pos, black_pos - 1, 0)
    result = b.is_valid_move(m, "W")
    assert result is not True


def test_is_valid_move_invalid_arrow_part():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    b.arrow_bb = 1 << 2   # blocks arrow destination
    # queen moves from 0 to 1 (valid), but arrow to 2 is now blocked by
    # the queen occupying 1 after movement — let's block pos 3 and aim at 3
    b.arrow_bb |= 1 << 3
    m = Move(0, 1, 3)   # arrow blocked
    result = b.is_valid_move(m, "W")
    assert result is not True


# ---- MOVE_QUEEN ----


def test_move_queen_white():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    b.move_queen(0, 3, "W")
    assert b.white_bb & (1 << 0) == 0
    assert b.white_bb & (1 << 3) != 0


def test_move_queen_black():
    b = _empty_board(4)
    b.black_bb = 1 << 15
    b.move_queen(15, 12, "B")
    assert b.black_bb & (1 << 15) == 0
    assert b.black_bb & (1 << 12) != 0


# ---- PLACE_ARROW ----


def test_place_arrow_sets_bit():
    b = _empty_board(4)
    b.place_arrow(7)
    assert b.arrow_bb & (1 << 7) != 0


def test_place_arrow_idempotent():
    b = _empty_board(4)
    b.place_arrow(7)
    b.place_arrow(7)
    assert b.arrow_bb.bit_count() == 1


# ---- MAKE_MOVE / PLAY_MOVE / UNDO_MOVE ----


def test_make_move_white():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    b.make_move(Move(0, 1, 2), "W")
    assert b.white_bb & (1 << 0) == 0
    assert b.white_bb & (1 << 1) != 0
    assert b.arrow_bb & (1 << 2) != 0


def test_make_move_black():
    b = _empty_board(4)
    b.black_bb = 1 << 15
    b.make_move(Move(15, 14, 13), "B")
    assert b.black_bb & (1 << 15) == 0
    assert b.black_bb & (1 << 14) != 0
    assert b.arrow_bb & (1 << 13) != 0


def test_play_move_auto_detects_white():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    b.play_move(Move(0, 1, 2))
    assert b.white_bb & (1 << 1) != 0


def test_play_move_auto_detects_black():
    b = _empty_board(4)
    b.black_bb = 1 << 15
    b.play_move(Move(15, 14, 13))
    assert b.black_bb & (1 << 14) != 0


def test_play_move_no_queen_raises():
    b = _empty_board(4)
    with pytest.raises(ValueError):
        b.play_move(Move(5, 6, 7))


def test_undo_move_white_restores_state():
    b = _empty_board(4)
    b.white_bb = 1 << 0
    m = Move(0, 1, 2)
    b.make_move(m, "W")
    b.undo_move(m, "W")
    assert b.white_bb & (1 << 0) != 0
    assert b.white_bb & (1 << 1) == 0
    assert b.arrow_bb & (1 << 2) == 0


def test_undo_move_black_restores_state():
    b = _empty_board(4)
    b.black_bb = 1 << 15
    m = Move(15, 14, 13)
    b.make_move(m, "B")
    b.undo_move(m, "B")
    assert b.black_bb & (1 << 15) != 0
    assert b.black_bb & (1 << 14) == 0
    assert b.arrow_bb & (1 << 13) == 0


def test_make_undo_roundtrip_preserves_board():
    b = Board(6)
    white_before = b.white_bb
    black_before = b.black_bb
    arrow_before = b.arrow_bb
    move = next(b.get_legal_moves("W"))
    b.make_move(move, "W")
    b.undo_move(move, "W")
    assert b.white_bb == white_before
    assert b.black_bb == black_before
    assert b.arrow_bb == arrow_before


# ---- CALCULATE_TERRITORY_SCORES ----


def test_territory_scores_positive_initial():
    b = Board(10)
    ws, bs = b.calculate_territory_scores()
    assert ws > 0
    assert bs > 0


def test_territory_scores_symmetric_initial():
    b = Board(10)
    ws, bs = b.calculate_territory_scores()
    assert ws == bs


def test_territory_scores_type():
    b = Board(6)
    ws, bs = b.calculate_territory_scores()
    assert isinstance(ws, int)
    assert isinstance(bs, int)


def test_territory_scores_each_le_empty_squares():
    b = Board(10)
    empty = 10 * 10 - b.occupied().bit_count()
    ws, bs = b.calculate_territory_scores()
    assert ws <= empty
    assert bs <= empty
