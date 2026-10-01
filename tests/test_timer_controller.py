from types import SimpleNamespace

from amazons.controller.engine import timer_controller


def _make_controller():
    return SimpleNamespace(
        timers={"W": 12.5, "B": 7.0},
        server=SimpleNamespace(client_socket=None, send=lambda payload: payload),
        client=SimpleNamespace(connected=False, send=lambda payload: payload),
    )


def test_normalize_clock_color_handles_empty_and_normalizes():
    assert timer_controller.normalize_clock_color(None) is None
    assert timer_controller.normalize_clock_color("") is None
    assert timer_controller.normalize_clock_color("white") == "W"
    assert timer_controller.normalize_clock_color("B") == "B"


def test_apply_remote_clock_update_updates_timer_and_clamps_to_zero():
    controller = _make_controller()

    assert timer_controller.apply_remote_clock_update(controller, "white", "-4") is True
    assert controller.timers["W"] == 0.0


def test_apply_remote_clock_update_rejects_invalid_values():
    controller = _make_controller()

    assert timer_controller.apply_remote_clock_update(controller, "white", "oops") is False
    assert timer_controller.apply_remote_clock_update(controller, "invalid", "2.0") is False
    assert controller.timers["W"] == 12.5


def test_apply_remote_clock_message_parses_valid_message():
    controller = _make_controller()

    assert timer_controller.apply_remote_clock_message(controller, "CLOCK B 3.75") is True
    assert controller.timers["B"] == 3.75


def test_apply_remote_clock_message_rejects_bad_message():
    controller = _make_controller()

    assert timer_controller.apply_remote_clock_message(controller, "CLOCK W") is False
    assert timer_controller.apply_remote_clock_message(controller, "HELLO") is False


def test_send_clock_update_prefers_server_socket():
    payloads = []
    controller = _make_controller()
    controller.server = SimpleNamespace(
        client_socket=object(),
        send=lambda payload: payloads.append(payload) or True,
    )

    assert timer_controller.send_clock_update(controller, "W") is True
    assert payloads == ["CLOCK W 12.500"]


def test_send_clock_update_falls_back_to_client():
    payloads = []
    controller = _make_controller()
    controller.client = SimpleNamespace(
        connected=True,
        send=lambda payload: payloads.append(payload) or "sent",
    )

    assert timer_controller.send_clock_update(controller, "black") == "sent"
    assert payloads == ["CLOCK B 7.000"]


def test_send_clock_update_returns_false_without_connection_or_color():
    controller = _make_controller()

    assert timer_controller.send_clock_update(controller, "???") is False
    assert timer_controller.send_clock_update(controller, None) is False


def test_get_time_status_line_formats_both_timers():
    controller = _make_controller()

    assert timer_controller.get_time_status_line(controller, lambda text: text) == (
        "Time remaining -> White: 12.5s | Black: 7.0s"
    )
