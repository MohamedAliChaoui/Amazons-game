"""Helpers for creating players in the game controller."""

import time

from amazons.model.players.ai_player import AIPlayer
from amazons.model.players.human_player import human_player
from amazons.model.players.player import NetworkPlayer


def _split_name_entry(entry):
    """Split a ``name,surname`` input into two trimmed parts."""
    if "," in entry:
        first, second = entry.split(",", 1)
    else:
        first, second = entry, ""
    return first.strip(), second.strip()


def create_players(controller, translator, adversaire):
    """Create the two player objects according to the selected mode."""
    if adversaire == "hu":
        entree1 = controller.cli.input_cli(
            "Player 1 name and surname (white) (format: name,surname): "
        )
        entree2 = controller.cli.input_cli(
            "Player 2 name and surname (black) (format: name,surname): "
        )

        nom1, prenom1 = _split_name_entry(entree1)
        nom2, prenom2 = _split_name_entry(entree2)

        controller.players = [
            human_player(nom1, prenom1, "W"),
            human_player(nom2, prenom2, "B"),
        ]

    elif adversaire == "ai":
        entree1 = controller.cli.input_cli(
            "Player 1 name and surname (white) (format: name,surname): "
        )
        nom1, prenom1 = _split_name_entry(entree1)

        bot_name = f"AIBot[{controller.ai_mode}]"
        joueur2 = AIPlayer(
            bot_name,
            "B",
            ai_mode=controller.ai_mode,
            ai_depth=controller.ai_depth,
            ai_evaluator=controller.ai_evaluator,
        )

        controller.cli.msg(
            translator(f"L'IA ({bot_name}) a rejoint la partie en tant que Black.")
        )

        controller.players = [
            human_player(nom1, prenom1, "W"),
            joueur2,
        ]

    elif adversaire == "aiai":
        bot_white = AIPlayer(
            f"AIBotWhite[{controller.ai_mode}]",
            "W",
            ai_mode=controller.ai_mode,
            ai_depth=controller.ai_depth,
            ai_evaluator=controller.ai_evaluator,
        )

        bot_black = AIPlayer(
            f"AIBotBlack[{controller.ai_mode}]",
            "B",
            ai_mode=controller.ai_mode,
            ai_depth=controller.ai_depth,
            ai_evaluator=controller.ai_evaluator,
        )

        controller.cli.msg(translator(f"{bot_white.nom} joue White."))
        controller.cli.msg(translator(f"{bot_black.nom} joue Black."))

        controller.players = [bot_white, bot_black]

    elif adversaire == "network":
        host_player = getattr(controller.server, "host_player", None)
        nom_host = ""
        if isinstance(host_player, dict):
            nom_host = (host_player.get("name") or "").strip()
        if not nom_host:
            nom_host = controller.cli.input_cli(
                translator("Your name (White): ")
            ).strip()
        controller.server.set_host_player(nom_host, status="idle")
        controller.players = [
            human_player(nom_host, "", "W"),
            NetworkPlayer(
                "Remote",
                "B",
                controller.server,
                on_clock_received=controller._apply_remote_clock_update,
            ),
        ]
        if not controller.server.send(
            f"START {controller.size} WHITE {controller.time_limit_per_move:.3f}"
        ):
            controller.cli.msg(
                translator("Remote player disconnected before game start.")
            )
            return False
        if not controller.server.send(f"NAME {nom_host}"):
            controller.cli.msg(
                translator("Remote player disconnected before name exchange.")
            )
            return False

        controller.cli.msg(translator("Waiting for remote player name..."))
        start_wait = time.time()
        client_name_found = False
        while time.time() - start_wait < 30 and not client_name_found:
            if controller.server.inbox:
                for i, msg in enumerate(controller.server.inbox):
                    if msg.upper().startswith("NAME "):
                        client_name = controller.server.inbox.pop(i)[5:].strip()
                        controller.players[1].nom = client_name
                        controller.server.begin_hosted_game(
                            nom_host,
                            player_id=controller.server.active_player_id,
                        )
                        controller.server.inbox = [
                            pending
                            for pending in controller.server.inbox
                            if not pending.upper().startswith(
                                ("HOST_START_GAME", "INVITE_ACCEPTED ")
                            )
                        ]
                        controller.cli.msg(
                            translator("Remote player identified as: {name}").format(
                                name=client_name
                            )
                        )
                        client_name_found = True
                        break
            time.sleep(0.1)

        if not client_name_found:
            controller.cli.msg(
                translator(
                    "Remote player did not send a name in time. "
                    "Game start cancelled."
                )
            )
            return False

    else:
        return False

    return True
