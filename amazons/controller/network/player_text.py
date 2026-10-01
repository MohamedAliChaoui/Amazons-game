"""Formatting helpers for network player display strings."""


def format_connected_player_line(player, translator):
    """Return a translated single-line summary for one connected player."""
    host, port = player["address"]
    return translator("{id}: {name} | {status} | {host}:{port}").format(
        id=player["id"],
        name=player["name"],
        status=player["status"],
        host=host,
        port=port,
    )
