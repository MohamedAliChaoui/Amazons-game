import os
import pytest
from amazons.controller.engine.game_controller import GameController
from amazons.model.players.human_player import HumanPlayer
from amazons.model.board.move import Move
from amazons.controller.save_load_manager import SaveLoadManager


@pytest.fixture
def fake_save_file(tmp_path):
    return os.path.join(tmp_path, "save_test.amz")


def test_save_and_load(fake_save_file):
    # 1. Setup GameController
    gc1 = GameController(
        size=6, time_limit_min=10.0, ai_mode="mcts", ai_time=2.0
    )
    # mock players configuration
    gc1.players = [
        HumanPlayer("W", "Alice", "W"),
        HumanPlayer("B", "Bob", "B"),
    ]

    # 4 queens each side (Amazons rule), no overlap, 1 arrow
    gc1.board.white_bb = 0b00001111          # bits 0-3
    gc1.board.black_bb = 0b11110000          # bits 4-7
    gc1.board.arrow_bb = 1 << 8             # bit 8 (1 arrow matches 1 history entry)

    start = Move.from_algebraic("a1", 6)
    end = Move.from_algebraic("a2", 6)
    arrow = Move.from_algebraic("a3", 6)
    m = Move(start, end, arrow)
    gc1.history.append((m, "W"))

    # 3. Save
    success, msg = SaveLoadManager.save_game(gc1, fake_save_file)
    assert success is True
    assert os.path.exists(fake_save_file)

    # 4. Load into a new GameController
    gc2 = GameController()
    success, msg = SaveLoadManager.load_game(gc2, fake_save_file)
    assert success is True

    # 5. Assertions
    assert gc2.size == 6
    assert gc2.time_limit_per_move == 600.0
    assert gc2.ai_mode == "mcts"
    assert gc2.ai_time == 2.0
    assert gc2.board.white_bb == gc1.board.white_bb
    assert gc2.board.black_bb == gc1.board.black_bb
    assert gc2.board.arrow_bb == gc1.board.arrow_bb
    assert len(gc2.history) == 1

    loaded_move, loaded_color = gc2.history[0]
    assert loaded_color == "W"
    assert loaded_move.start_pos == start
    assert loaded_move.end_pos == end
    assert loaded_move.arrow_pos == arrow


def test_load_nonexistent_file():
    gc = GameController()
    success, msg = SaveLoadManager.load_game(gc, "does_not_exist_at_all.amz")
    assert success is False
    assert "File not found" in msg


def test_invalid_algebraic_in_history(fake_save_file):
    with open(fake_save_file, "w", encoding="utf-8") as f:
        f.write("[history]\n1. W invalid-move/stuff;")

    gc = GameController()
    success, msg = SaveLoadManager.load_game(gc, fake_save_file)
    assert success is True
    assert len(gc.history) == 0  # Should gracefully ignore


def test_comments_removal(fake_save_file):
    # Validate comment stripping logic
    content = "{Block comment} [settings] # inline comment\nsize=8"
    with open(fake_save_file, "w", encoding="utf-8") as f:
        f.write(content)

    gc = GameController()
    SaveLoadManager.load_game(gc, fake_save_file)
    assert gc.size == 8


def test_load_game_from_text_accepts_valid_4x4_board():
    source = GameController(size=4)
    raw = SaveLoadManager.serialize_game_state(
        size=4,
        time_limit_per_move=source.time_limit_per_move,
        board=source.board,
        history=[],
        ai_mode=source.ai_mode,
        ai_time=source.ai_time,
        ai_evaluator=source.ai_evaluator,
    )

    target = GameController()
    success, msg = SaveLoadManager.load_game_from_text(target, raw)

    assert success is True
    assert target.size == 4


def test_load_game_from_text_accepts_valid_5x5_board():
    source = GameController(size=5)
    raw = SaveLoadManager.serialize_game_state(
        size=5,
        time_limit_per_move=source.time_limit_per_move,
        board=source.board,
        history=[],
        ai_mode=source.ai_mode,
        ai_time=source.ai_time,
        ai_evaluator=source.ai_evaluator,
    )

    target = GameController()
    success, msg = SaveLoadManager.load_game_from_text(target, raw)

    assert success is True
    assert target.size == 5


# ---- CHECKSUM ----


def test_compute_checksum_deterministic():
    h1 = SaveLoadManager._compute_checksum("hello world")
    h2 = SaveLoadManager._compute_checksum("hello world")
    assert h1 == h2


def test_compute_checksum_different_for_different_content():
    h1 = SaveLoadManager._compute_checksum("abc")
    h2 = SaveLoadManager._compute_checksum("xyz")
    assert h1 != h2


def test_compute_checksum_is_hex_string():
    h = SaveLoadManager._compute_checksum("test")
    assert len(h) == 64
    int(h, 16)  # raises if not valid hex


def test_verify_checksum_valid():
    content = "[settings]\nsize=6\n"
    checksum = SaveLoadManager._compute_checksum(content)
    raw = content + "\n[checksum]\n" + checksum + "\n"
    ok, msg = SaveLoadManager._verify_checksum(raw)
    assert ok is True


def test_verify_checksum_tampered_content():
    content = "[settings]\nsize=6\n"
    checksum = SaveLoadManager._compute_checksum(content)
    raw = content + "\n[checksum]\n" + checksum + "\n"
    # tamper: change size
    raw_tampered = raw.replace("size=6", "size=10")
    ok, msg = SaveLoadManager._verify_checksum(raw_tampered)
    assert ok is False
    assert "modified" in msg


def test_verify_checksum_bad_hash():
    content = "[settings]\nsize=6\n"
    raw = content + "\n[checksum]\nbadbadhash\n"
    ok, msg = SaveLoadManager._verify_checksum(raw)
    assert ok is False


def test_verify_checksum_missing_section():
    raw = "[settings]\nsize=6\n"
    ok, msg = SaveLoadManager._verify_checksum(raw)
    assert ok is False
    assert "Missing" in msg


# ---- STRIP CHECKSUM SECTION ----


def test_strip_checksum_section_removes_it():
    raw = "[settings]\nsize=6\n\n[checksum]\nabc123\n"
    stripped = SaveLoadManager._strip_checksum_section(raw)
    assert "[checksum]" not in stripped
    assert "size=6" in stripped


def test_strip_checksum_section_no_checksum_unchanged():
    raw = "[settings]\nsize=6\n"
    stripped = SaveLoadManager._strip_checksum_section(raw)
    assert stripped == raw


# ---- REMOVE BLOCK COMMENTS ----


def test_remove_block_comments_basic():
    result = SaveLoadManager._remove_block_comments("before{ignored}after")
    assert result == "beforeafter"


def test_remove_block_comments_multiple():
    result = SaveLoadManager._remove_block_comments("{a}hello{b}world{c}")
    assert result == "helloworld"


def test_remove_block_comments_no_comment_unchanged():
    text = "no comments here"
    assert SaveLoadManager._remove_block_comments(text) == text


def test_remove_block_comments_multiline():
    text = "start\n{this\nis\na comment\n}end"
    result = SaveLoadManager._remove_block_comments(text)
    assert result == "start\nend"


# ---- VALIDATE BOARD ----


def test_validate_board_no_white_queens():
    gc = GameController()
    gc.board.white_bb = 0
    gc.board.black_bb = 0b11110000
    gc.board.arrow_bb = 0
    gc.history = []
    ok, msg = SaveLoadManager._validate_board(gc)
    assert ok is False
    assert "white" in msg.lower()


def test_validate_board_no_black_queens():
    gc = GameController()
    gc.board.white_bb = 0b00001111
    gc.board.black_bb = 0
    gc.board.arrow_bb = 0
    gc.history = []
    ok, msg = SaveLoadManager._validate_board(gc)
    assert ok is False
    assert "black" in msg.lower()


def test_validate_board_count_mismatch():
    gc = GameController()  # size=10, expects 4 queens each
    gc.board.white_bb = 0b00001111   # 4 queens
    gc.board.black_bb = 0b00010000   # 1 queen
    gc.board.arrow_bb = 0
    gc.history = []
    ok, msg = SaveLoadManager._validate_board(gc)
    assert ok is False


def test_validate_board_overlap():
    gc = GameController()
    # white: bits 0-3, black: bits 1-4 → overlap at bits 1,2,3
    gc.board.white_bb = 0b00001111
    gc.board.black_bb = 0b00011110
    gc.board.arrow_bb = 0
    gc.history = []
    ok, msg = SaveLoadManager._validate_board(gc)
    assert ok is False
    assert "overlap" in msg.lower()


def test_validate_board_arrow_history_mismatch():
    gc = GameController(size=6)
    # standard board has 0 arrows; add 1 history entry → mismatch
    gc.history = [(Move(0, 1, 2), "W")]
    ok, msg = SaveLoadManager._validate_board(gc)
    assert ok is False
    assert "arrow" in msg.lower()


def test_validate_board_wrong_queen_count_for_size():
    gc = GameController(size=10)  # expects 4 queens each
    gc.board.white_bb = 0b00000111   # 3 queens
    gc.board.black_bb = 0b00111000   # 3 queens
    gc.board.arrow_bb = 0
    gc.history = []
    ok, msg = SaveLoadManager._validate_board(gc)
    assert ok is False
    assert "expected" in msg.lower()


# ---- LOAD WITH INVALID SIZE ----


def test_load_invalid_size_too_small():
    raw = "[settings]\nsize=3\n[game]\nW\n_ _\n_ _\n"
    gc = GameController()
    ok, msg = SaveLoadManager.load_game_from_text(gc, raw)
    assert ok is False
    assert "3" in msg


def test_load_invalid_size_too_large():
    rows = "\n".join(["_ " * 12] * 12)
    raw = f"[settings]\nsize=12\n[game]\nW\n{rows}\n"
    gc = GameController()
    ok, msg = SaveLoadManager.load_game_from_text(gc, raw)
    assert ok is False


# ---- TAMPERED CHECKSUM IN LOAD ----


def test_load_game_from_text_tampered_checksum():
    source = GameController(size=6)
    content = SaveLoadManager.serialize_game_state(
        size=6,
        time_limit_per_move=source.time_limit_per_move,
        board=source.board,
        history=[],
    )
    raw = content + "\n[checksum]\nbadchecksum\n"
    gc = GameController()
    ok, msg = SaveLoadManager.load_game_from_text(gc, raw)
    assert ok is False
    assert "modified" in msg


def test_load_game_from_text_skip_checksum_overrides_bad_hash():
    source = GameController(size=6)
    content = SaveLoadManager.serialize_game_state(
        size=6,
        time_limit_per_move=source.time_limit_per_move,
        board=source.board,
        history=[],
    )
    raw = content + "\n[checksum]\nbadchecksum\n"
    gc = GameController()
    ok, msg = SaveLoadManager.load_game_from_text(gc, raw, skip_checksum=True)
    assert ok is True


# ---- SERIALIZE WITH AI OPTIONS ----


def test_serialize_includes_ai_mode_and_evaluator():
    source = GameController(size=6)
    content = SaveLoadManager.serialize_game_state(
        size=6,
        time_limit_per_move=300,
        board=source.board,
        history=[],
        ai_mode="minimax",
        ai_time=5.0,
        ai_evaluator="territory",
    )
    assert "ai-mode=minimax" in content
    assert "ai-time=5.0" in content
    assert "ai-minimax-scoring=territory" in content


def test_serialize_omits_ai_mode_when_none():
    source = GameController(size=6)
    content = SaveLoadManager.serialize_game_state(
        size=6,
        time_limit_per_move=300,
        board=source.board,
        history=[],
    )
    assert "ai-mode" not in content
    assert "ai-minimax-scoring" not in content


# ---- SAVE TO INVALID PATH ----


def test_save_to_invalid_path_returns_failure():
    gc = GameController(size=6)
    ok, msg = SaveLoadManager.save_game(gc, "/nonexistent/path/file.amz")
    assert ok is False
    assert "Failed" in msg


# ---- FULL ROUND-TRIP WITH CHECKSUM ----


def test_save_load_checksum_roundtrip(fake_save_file):
    gc1 = GameController(size=6)
    gc1.board.white_bb = 0b00001111
    gc1.board.black_bb = 0b11110000
    gc1.board.arrow_bb = 0
    gc1.history = []

    ok, _ = SaveLoadManager.save_game(gc1, fake_save_file)
    assert ok is True

    with open(fake_save_file) as f:
        raw = f.read()
    assert "[checksum]" in raw

    gc2 = GameController()
    ok, msg = SaveLoadManager.load_game(gc2, fake_save_file)
    assert ok is True
