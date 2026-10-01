"""Display and reporting helpers for the main game controller."""

from amazons.controller.network.player_text import format_connected_player_line


def get_history_lines(controller):
    """Build a list of history lines in the save-file format."""
    if not controller.history:
        return ["No moves played yet."]

    lines = []

    for index in range(0, len(controller.history), 2):
        turn_number = index // 2 + 1
        turn_moves = [
            f"{controller.format_move_notation(move, color)};"
            for move, color in controller.history[index:index + 2]
        ]
        lines.append(f"{turn_number}. " + " ".join(turn_moves))

    return lines


def get_configuration_lines(controller, translator):
    """Return a list of strings describing current settings."""
    return [
        translator("Board size: {size}").format(size=controller.size),
        translator("AI mode: {mode}").format(mode=controller.ai_mode),
        translator("AI time limit: {time}s").format(
            time=f"{controller.ai_time:.1f}"
        ),
        translator("AI minimax depth: {depth}").format(
            depth=controller.ai_depth
        ),
        translator("AI evaluator: {evaluator}").format(
            evaluator=controller.ai_evaluator
        ),
        translator("Player time limit: {time} min").format(
            time=f"{controller.time_limit_per_move / 60:.1f}"
        ),
    ]


def show_history(controller, translator):
    """Print the move history to the CLI."""
    controller.cli.msg(translator("History:"))
    for line in get_history_lines(controller):
        controller.cli.msg(line)


def show_time(controller, translator):
    """Print the remaining time for each player."""
    if controller.is_start_party is True:
        controller.cli.msg(controller.get_time_status_line())
    else:
        print(translator("The game has not started yet."))


def show_configuration(controller, translator):
    """Print the current configuration settings."""
    controller.cli.msg(translator("Configuration:"))
    for line in get_configuration_lines(controller, translator):
        controller.cli.msg(line)


def show_server_status(controller, translator):
    """Print the current server status summary."""
    server_status = controller.server.get_status()
    controller.cli.msg(translator("\n--- SERVER STATUS ---"))
    controller.cli.msg(
        translator("Listening port: {port}").format(port=server_status["port"])
    )
    controller.cli.msg(
        translator("Connected clients: {count}").format(
            count=server_status["connected_clients"]
        )
    )
    controller.cli.msg(
        translator("Parties in progress: {count}").format(
            count=server_status["parties_in_progress"]
        )
    )
    active_id = server_status["active_player_id"] or "-"
    controller.cli.msg(
        translator("Active player: {player_id}").format(player_id=active_id)
    )


def show_players(controller, translator, player_id=None):
    """Print connected players or details for one player."""
    if player_id:
        player = controller.server.get_player(player_id.upper())
        if not player:
            controller.cli.msg(translator("Unknown player ID."))
            return

        controller.cli.msg(
            translator("Player {player}").format(
                player=format_connected_player_line(player, translator)
            )
        )
        return

    players = controller.server.get_players()
    if not players:
        controller.cli.msg(translator("No players connected."))
        return

    controller.cli.msg(translator("\n--- CONNECTED PLAYERS ---"))
    for player in players:
        controller.cli.msg(format_connected_player_line(player, translator))


def show_scoreboard(controller, translator):
    """Print the current network scoreboard."""
    entries = controller.server.get_scoreboard()
    if not entries:
        controller.cli.msg(translator("Scoreboard is empty."))
        return

    controller.cli.msg(translator("\n--- SCOREBOARD ---"))
    for entry in entries:
        controller.cli.msg(
            translator(
                "{name}: {wins} win(s), {losses} loss(es), {played} game(s)"
            ).format(
                name=entry["name"],
                wins=entry["wins"],
                losses=entry["losses"],
                played=entry["played"],
            )
        )
