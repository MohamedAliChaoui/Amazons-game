"""Helpers for move hints and legal-move previews."""

from amazons.model.board.move import Move


def handle_hint_command(controller, translator, color_code):
    """Compute and display a hint move using the AI."""
    controller.cli.msg(translator("Calculating hint... please wait."))
    ai_mode = controller.ai_mode or "minimax"
    ai_time = controller.ai_time or 5.0
    depth = controller.ai_depth or 3
    evaluator = controller.ai_evaluator or "hybrid"

    from amazons.model.ai.utils import create_ai_engine
    engine = create_ai_engine(ai_mode, ai_time, depth, evaluator)

    move = engine.best_move(controller.board, color_code)
    if move is None:
        controller.cli.msg(translator("No legal move available."))
        return

    if isinstance(move, str):
        notation = move
    else:
        s_alg = Move.to_algebraic(move.start_pos, controller.size)
        e_alg = Move.to_algebraic(move.end_pos, controller.size)
        a_alg = Move.to_algebraic(move.arrow_pos, controller.size)
        notation = f"{s_alg}-{e_alg}/{a_alg}"

    controller.cli.msg(
        translator(
            f"Hint: The AI suggests {color_code} "
            f"{notation}"
        )
    )


def show_possible_moves(controller, translator, action, joueur):
    """Show legal moves from a chosen square."""
    parts = action.split()
    if len(parts) < 2:
        controller.cli.msg(translator("Usage: choice <case> (ex: choice d4)"))
        return

    try:
        start_pos = Move.from_algebraic(parts[1], controller.size)
        occupied = controller.board.occupied()

        if joueur.couleur == "W":
            if not (controller.board.white_bb & (1 << start_pos)):
                controller.cli.msg(translator(f"No white piece at {parts[1]}"))
                return
        elif joueur.couleur == "B":
            if not (controller.board.black_bb & (1 << start_pos)):
                controller.cli.msg(translator(f"No black piece at {parts[1]}"))
                return

        targets = list(
            controller.board.get_queen_moves_iterator(start_pos, occupied)
        )
        highlights = [(pos // controller.size, pos % controller.size) for pos in targets]

        controller.cli.msg(
            translator(f"Moves possible from {parts[1]}: {len(targets)}")
        )
        controller.cli.show_board_possible_moves(
            controller.board.get_board_array(), highlights
        )
    except (ValueError, IndexError):
        controller.cli.msg(
            translator(
                "Invalid coordinates. Use algebraic notation "
                "(e.g., a1, d4)."
            )
        )
