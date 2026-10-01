import pytest
from amazons.model.board.board import Board
from amazons.model.board.move import Move

# --- 1. SCALABILITY TESTS (4 TO 11) ---


@pytest.mark.parametrize("size", range(4, 11))  # --- RANGE12
def test_mobility_all_sizes_empty_board(size):
    """Checks queen mobility in corner (0,0) for each board size."""
    b = Board(size)
    b.white_bb = 0
    b.black_bb = 0
    b.arrow_bb = 0

    moves = list(b.get_queen_moves_iterator(0, 0))
    expected = 3 * (size - 1)
    assert len(moves) == expected, f"Mobility failed on {size}x{size} board"


# --- 2. COLLISION AND OBSTACLE TESTS ---


def test_collision_all_types():
    """Checks that no obstacle (Ally, Enemy, Arrow) can be passed through."""
    size = 10
    b = Board(size)
    start = 5 * size + 5
    b.white_bb = 1 << start

    b.white_bb |= 1 << (5 * size + 7)  # Ally queen blocks right
    b.black_bb = 1 << (5 * size + 3)  # Enemy queen blocks left
    b.arrow_bb = 1 << (7 * size + 5)  # Arrow blocks down

    occupied = b.occupied()
    moves = list(b.get_queen_moves_iterator(start, occupied))

    assert 5 * size + 7 not in moves, "Ally collision not detected"
    assert 5 * size + 8 not in moves, "Jump over ally not detected"
    assert 5 * size + 3 not in moves, "Enemy collision not detected"
    assert 7 * size + 5 not in moves, "Arrow collision not detected"


# --- 3. MOVEMENT LOGIC TESTS ---


def test_illegal_trajectory():
    """Checks that non-orthogonal/diagonal moves are rejected."""
    b = Board(10)
    move = Move(0, 12, 13)
    assert b.is_valid_move(move, "W") is not True


def test_shoot_at_start_position():
    """Checks that you can shoot an arrow at the square you just left."""
    b = Board(10)
    b.white_bb = 1 << 0
    move = Move(0, 1, 0)
    assert b.is_valid_move(move, "W") is True


# --- 4. SATURATION AND SECURITY TESTS ---


def test_complete_asphyxiation():
    """Checks that get_legal_moves is empty when a queen is trapped."""
    size = 4
    b = Board(size)
    b.white_bb = 1 << 5
    surrounding = [0, 1, 2, 4, 6, 8, 9, 10]
    for pos in surrounding:
        b.arrow_bb |= 1 << pos

    moves = list(b.get_legal_moves("W"))
    assert len(moves) == 0, "No moves should be possible"


def test_move_opponent_queen_forbidden():
    """Checks that a player cannot move an opponent's queen."""
    b = Board(10)
    b.black_bb = 1 << 0  # Black Queen at (0,0)
    move = Move(0, 1, 2)  # White player attempts to move it
    assert b.is_valid_move(move, "W") is not True
