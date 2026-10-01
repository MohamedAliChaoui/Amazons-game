"""Helpers for network notifications handled by the game controller."""


def is_player_id(token):
    """Return ``True`` if *token* looks like a server player id."""
    if not token:
        return False
    value = token.strip().upper()
    return value.startswith("P") and value[1:].isdigit()


def _reset_network_flags(controller):
    """Reset network callbacks and flags after a disconnection event."""
    controller.server.on_message_received = None
    controller.client.on_message_received = None
    controller.is_start_party = False
    controller.pending_network_host_start = False
    controller.network_host_starting = False


def handle_network_notification(controller, translator, message):
    """Display invitation and server-side network notifications."""
    parts = message.split(maxsplit=2)
    command = parts[0].upper()

    if command == "INVITE_FROM" and len(parts) >= 3:
        controller.cli.msg(
            translator(
                "Invitation received from {player_id} ({name}). "
                "Use accept or decline."
            ).format(player_id=parts[1], name=parts[2])
        )
        return True
    if command == "PLAYER_CONNECTED" and len(parts) >= 3:
        controller.cli.msg(
            translator(
                "PLayer is connected to your server,you can now either start a game with 'new network' or "
                "type 'players' and choose a player with "
                "'new PLAYER_ID'."
            )
        )
        return True
    if command == "INVITE_SENT" and len(parts) >= 3:
        controller.cli.msg(
            translator("Invitation sent to {player_id} ({name}).").format(
                player_id=parts[1], name=parts[2]
            )
        )
        return True
    if command == "INVITE_ACCEPTED" and len(parts) >= 3:
        controller.cli.msg(
            translator("Invitation accepted by {player_id} ({name}).").format(
                player_id=parts[1], name=parts[2]
            )
        )
        return True
    if command == "INVITE_DECLINED" and len(parts) >= 3:
        controller.cli.msg(
            translator("Invitation declined by {player_id} ({name}).").format(
                player_id=parts[1], name=parts[2]
            )
        )
        return True
    if command == "INVITE_CANCELLED" and len(parts) >= 3:
        controller.cli.msg(
            translator("Invitation cancelled by {player_id} ({name}).").format(
                player_id=parts[1], name=parts[2]
            )
        )
        return True
    if command == "INVITE_EXPIRED" and len(parts) >= 3:
        controller.cli.msg(
            translator(
                "Invitation expired between you and {player_id} ({name})."
            ).format(player_id=parts[1], name=parts[2])
        )
        return True
    if command == "CLIENT_MATCH_STARTED" and len(parts) >= 3:
        controller.cli.msg(
            translator(
                "Started a client match between {player_one} and {player_two}."
            ).format(
                player_one=parts[1],
                player_two=parts[2],
            )
        )
        return True
    if command == "ERROR" and len(parts) >= 2:
        controller.cli.msg(parts[1] if len(parts) == 2 else f"{parts[1]} {parts[2]}")
        return True
    if command == "SERVER_STOP":
        controller.cli.msg(
            translator(
                controller.client.disconnect_reason
                or "Server stopped and closed the session."
            )
        )
        _reset_network_flags(controller)
        return True
    if command == "TIMEOUT":
        controller.cli.msg(
            translator(
                controller.client.disconnect_reason
                or "Disconnected after 60 seconds of inactivity."
            )
        )
        _reset_network_flags(controller)
        return True
    if command == "HOST_START_GAME" and len(parts) >= 2:
        setter = getattr(controller.server, "set_active_player", None)
        if callable(setter):
            setter(parts[1])
        else:
            try:
                controller.server.active_player_id = parts[1]
            except Exception:
                pass
        controller.pending_network_host_start = False
        if controller.is_start_party or controller.network_host_starting:
            return True
        controller.cli.msg(
            translator(
                "Invitation accepted. Starting network game with {player_id}..."
            ).format(player_id=parts[1])
        )
        controller.startGame("network")
        return True
    return False
