from types import SimpleNamespace

from amazons.controller.engine import network_notification_controller


class DummyCLI:
    def __init__(self):
        self.messages = []

    def msg(self, text):
        self.messages.append(text)


def _controller():
    cli = DummyCLI()
    controller = SimpleNamespace()
    controller.cli = cli
    controller.server = SimpleNamespace(
        on_message_received="server-callback",
        active_player_id=None,
        set_active_player=lambda player_id: cli.msg(f"set-active:{player_id}"),
    )
    controller.client = SimpleNamespace(
        on_message_received="client-callback",
        disconnect_reason=None,
    )
    controller.is_start_party = True
    controller.pending_network_host_start = True
    controller.network_host_starting = False
    controller.startGame = lambda mode: cli.msg(f"start:{mode}")
    return controller


def test_is_player_id_recognizes_expected_values():
    assert network_notification_controller.is_player_id("P12") is True
    assert network_notification_controller.is_player_id(" p7 ") is True
    assert network_notification_controller.is_player_id("HOST") is False
    assert network_notification_controller.is_player_id(None) is False


def test_reset_network_flags_clears_callbacks_and_state():
    controller = _controller()

    network_notification_controller._reset_network_flags(controller)

    assert controller.server.on_message_received is None
    assert controller.client.on_message_received is None
    assert controller.is_start_party is False
    assert controller.pending_network_host_start is False
    assert controller.network_host_starting is False


def test_handle_network_notification_formats_common_messages():
    controller = _controller()

    messages = [
        "INVITE_FROM P2 Sara",
        "PLAYER_CONNECTED P2 Sara",
        "INVITE_SENT P2 Sara",
        "INVITE_ACCEPTED P2 Sara",
        "INVITE_DECLINED P2 Sara",
        "INVITE_CANCELLED P2 Sara",
        "INVITE_EXPIRED P2 Sara",
        "CLIENT_MATCH_STARTED P1 P2",
    ]

    for msg in messages:
        assert network_notification_controller.handle_network_notification(
            controller, lambda text: text, msg
        ) is True

    assert any("Use accept or decline." in m for m in controller.cli.messages)
    assert any("new PLAYER_ID" in m for m in controller.cli.messages)
    assert any("Invitation sent" in m for m in controller.cli.messages)
    assert any("Invitation accepted by" in m for m in controller.cli.messages)
    assert any("Invitation declined by" in m for m in controller.cli.messages)
    assert any("Invitation cancelled by" in m for m in controller.cli.messages)
    assert any("Invitation expired" in m for m in controller.cli.messages)
    assert any("Started a client match" in m for m in controller.cli.messages)


def test_handle_network_notification_error_joins_tail():
    controller = _controller()

    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "ERROR Something bad"
    ) is True
    assert "Something bad" in controller.cli.messages


def test_handle_network_notification_server_stop_and_timeout_reset_flags():
    controller = _controller()
    controller.client.disconnect_reason = "bye"

    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "SERVER_STOP"
    ) is True
    assert controller.cli.messages[-1] == "bye"
    assert controller.server.on_message_received is None

    controller = _controller()
    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "TIMEOUT"
    ) is True
    assert any("Disconnected after 60 seconds of inactivity." in m for m in controller.cli.messages)
    assert controller.client.on_message_received is None


def test_handle_network_notification_host_start_uses_setter_and_starts_game():
    controller = _controller()
    controller.is_start_party = False
    controller.pending_network_host_start = True

    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "HOST_START_GAME P9"
    ) is True
    assert "set-active:P9" in controller.cli.messages
    assert "start:network" in controller.cli.messages


def test_handle_network_notification_host_start_falls_back_to_active_player_assignment():
    controller = _controller()
    controller.server = SimpleNamespace(
        on_message_received="server-callback",
        active_player_id=None,
    )
    controller.is_start_party = False
    controller.pending_network_host_start = True

    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "HOST_START_GAME P5"
    ) is True
    assert controller.server.active_player_id == "P5"
    assert "start:network" in controller.cli.messages


def test_handle_network_notification_host_start_skips_restart_when_already_starting():
    controller = _controller()
    controller.is_start_party = True

    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "HOST_START_GAME P4"
    ) is True
    assert "start:network" not in controller.cli.messages


def test_handle_network_notification_returns_false_for_unknown_message():
    controller = _controller()

    assert network_notification_controller.handle_network_notification(
        controller, lambda text: text, "HELLO"
    ) is False
