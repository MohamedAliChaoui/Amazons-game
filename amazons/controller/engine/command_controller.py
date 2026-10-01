"""Helpers for basic CLI command dispatch in the game controller."""


def resolve_opponent_type(controller, translator, parts):
    """Determine the opponent type from a ``new`` command."""
    if len(parts) == 1:
        return controller.cli.ask_opponent_type()

    if len(parts) > 2:
        controller.cli.msg(translator("Usage: new [hu|ai|aiai|network]"))
        return None

    mode = parts[1].lower()
    mapping = {
        "hu": "hu",
        "human": "hu",
        "ai": "ai",
        "aiai": "aiai",
        "network": "network",
    }

    if mode not in mapping:
        controller.cli.msg(
            translator("Unknown game mode. Use hu, ai, aiai or network.")
        )
        return None

    return mapping[mode]


def handle_show_command(controller, translator, parts):
    """Dispatch a ``show`` sub-command."""
    if not parts:
        return False

    cmd = parts[0]

    if cmd == "sb":
        controller.cli.show_board(controller.board.get_board_array())
        return True

    if cmd != "show":
        return False

    if len(parts) < 2:
        controller.cli.msg(
            translator("Usage: show board|history|time|configuration")
        )
        return True

    target = parts[1]
    if target == "board":
        controller.cli.show_board(controller.board.get_board_array())
    elif target == "history":
        controller.cli.show_history(controller.history, controller.size)
    elif target == "time":
        controller.show_time()
        return True
    elif target == "configuration":
        controller.show_configuration()
    else:
        controller.cli.msg(translator("Unknown show command"))

    return True
