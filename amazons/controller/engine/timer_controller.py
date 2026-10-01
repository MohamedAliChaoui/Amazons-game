"""Timer-related helpers used by the main game controller."""

from amazons.model.color import Color


def normalize_clock_color(color):
    """Normalize a color token to ``'W'`` or ``'B'``."""
    if not color:
        return None
    return Color.normalize(color)


def apply_remote_clock_update(controller, color, remaining):
    """Apply a remote clock value to the local timers."""
    try:
        color_key = normalize_clock_color(color)
    except ValueError:
        return False
    if not color_key:
        return False

    try:
        remaining_value = max(0.0, float(remaining))
    except (TypeError, ValueError):
        return False

    controller.timers[color_key] = remaining_value
    return True


def apply_remote_clock_message(controller, message):
    """Parse and apply a ``CLOCK`` protocol message."""
    parts = message.split(maxsplit=2)
    if len(parts) != 3:
        return False
    return apply_remote_clock_update(controller, parts[1], parts[2])


def send_clock_update(controller, color):
    """Send the current remaining time for one color to the peer."""
    try:
        color_key = normalize_clock_color(color)
    except ValueError:
        return False
    if not color_key:
        return False

    payload = f"CLOCK {color_key} {max(0.0, controller.timers[color_key]):.3f}"
    if controller.server.client_socket:
        return controller.server.send(payload)
    if controller.client.connected:
        return controller.client.send(payload)
    return False


def get_time_status_line(controller, translator):
    """Return a formatted string showing each player's remaining time."""
    return translator(
        "Time remaining -> White: {white:.1f}s | Black: {black:.1f}s"
    ).format(white=controller.timers["W"], black=controller.timers["B"])
