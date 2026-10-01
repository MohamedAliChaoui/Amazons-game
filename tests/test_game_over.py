from amazons.model.board.board import Board
from amazons.controller.engine.game_controller import GameController


def test_calculate_territory_scores_start_position():
    """
    au début de la partie, le score de territoire est de 0 tant qu'aucune zone
    n'est fermée ou atteignable.
    """
    b = Board(10)
    score_w, score_b = b.calculate_territory_scores()

    assert score_w > 0
    assert score_b > 0


def test_calculate_territory_scores_blocked_queen():
    """
    une reine complètement bloquée doit avoir un score de
    territoire de 0.
    """
    b = Board(4)
    b.white_bb = 1 << 0
    b.arrow_bb = (1 << 1) | (1 << 4) | (1 << 5)

    score_w, _ = b.calculate_territory_scores()

    assert score_w == 0, (
        "une reine bloquée devrait avoir un territoire de 0, "
        "mais le score obtenu est "
        f"{score_w}"
    )


def test_calculate_territory_scores_small_enclosure():
    """
    test du score de territoire quand une reine est enfermée dans une petite
    zone.
    """
    b = Board(4)
    b.white_bb = 1 << 0

    arrows = [2, 6, 10, 9, 8]
    for pos in arrows:
        b.arrow_bb |= 1 << pos

    score_w, _ = b.calculate_territory_scores()

    assert score_w == 3, (
        "3 cases vides étaient attendues pour le territoire, "
        "mais le score obtenu est "
        f"{score_w}"
    )


def test_game_over_by_blockade_white_loses():
    """
    la partie se termine quand le joueur blanc n'a plus de mouvements légaux.
    """
    gc = GameController(size=4)

    gc.board.white_bb = 1 << 0
    gc.board.arrow_bb = (1 << 1) | (1 << 4) | (1 << 5)

    legal_moves_w = list(gc.board.get_legal_moves("W"))
    assert len(legal_moves_w) == 0


def test_game_over_by_blockade_black_loses():
    """
    la partie se termine quand le joueur noir n'a plus de mouvements légaux.
    """
    gc = GameController(size=4)

    gc.board.black_bb = 1 << 0
    gc.board.arrow_bb = (1 << 1) | (1 << 4) | (1 << 5)

    legal_moves_b = list(gc.board.get_legal_moves("B"))
    assert len(legal_moves_b) == 0
