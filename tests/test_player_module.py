from unittest.mock import MagicMock

import pytest

from amazons.model.players.player import NetworkPlayer, Player


class DummyPlayer(Player):
    def get_action(self, board, time_limit=None):
        return "noop"


def test_player_color_properties_use_color_helpers():
    player = DummyPlayer("Alice", "W")

    assert player.color_code == "W"
    assert player.color_name == "white"


def test_network_player_returns_move_without_color_prefix(monkeypatch):
    network = MagicMock()
    network.receive.side_effect = ["MOVE We2-e4/e6"]
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer("Remote", "B", network)

    assert player.get_action(board=None) == "e2-e4/e6"


@pytest.mark.parametrize(
    "message, expected",
    [
        ("QUIT", "QUIT"),
        ("QUIT_GAME", "QUIT_GAME"),
        ("LOAD_STATE abc", "LOAD_STATE abc"),
        ("UNDO_REQ W", "UNDO_REQ W"),
        ("GAMEOVER blocked", "GAMEOVER"),
    ],
)
def test_network_player_returns_control_messages(monkeypatch, message, expected):
    network = MagicMock()
    network.receive.side_effect = [message]
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer("Remote", "B", network)

    assert player.get_action(board=None) == expected


def test_network_player_updates_name_and_clock_before_next_move(monkeypatch):
    network = MagicMock()
    network.receive.side_effect = [
        "NAME Karim",
        "CLOCK white 42.5",
        "MOVE Bc3-c4/c5",
    ]
    seen_names = []
    seen_clocks = []
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer(
        "Remote",
        "W",
        network,
        on_name_received=lambda name: seen_names.append(name),
        on_clock_received=lambda color, remaining: seen_clocks.append((color, remaining)),
    )

    assert player.get_action(board=None) == "c3-c4/c5"
    assert player.nom == "Karim"
    assert seen_names == ["Karim"]
    assert seen_clocks == [("white", "42.5")]


def test_network_player_ignores_invalid_clock_message_before_move(monkeypatch):
    network = MagicMock()
    network.receive.side_effect = [
        "CLOCK only-two-parts",
        "MOVE Wa1-a2/a3",
    ]
    seen_clocks = []
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer(
        "Remote",
        "W",
        network,
        on_clock_received=lambda color, remaining: seen_clocks.append((color, remaining)),
    )

    assert player.get_action(board=None) == "a1-a2/a3"
    assert seen_clocks == []


def test_network_player_without_callbacks_still_updates_name(monkeypatch):
    network = MagicMock()
    network.receive.side_effect = ["NAME Sara", "MOVE Wb1-b2/b3"]
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer("Remote", "W", network)

    assert player.get_action(board=None) == "b1-b2/b3"
    assert player.nom == "Sara"


def test_network_player_local_keyboard_undo(monkeypatch, capsys):
    class FakeMSVCRT:
        def __init__(self):
            self.chars = iter(["u", "n", "d", "o", "\r"])

        def kbhit(self):
            return True

        def getch(self):
            return next(self.chars).encode("ascii")

    network = MagicMock()
    network.receive.return_value = None
    monkeypatch.setattr("amazons.model.players.player.msvcrt", FakeMSVCRT())
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer("Remote", "B", network)

    assert player.get_action(board=None) == "LOCAL_UNDO"


def test_network_player_local_keyboard_invalid_command_then_quit(monkeypatch, capsys):
    class FakeMSVCRT:
        def __init__(self):
            self.chars = iter(["x", "\r", "q", "\r"])

        def kbhit(self):
            return True

        def getch(self):
            return next(self.chars).encode("ascii")

    network = MagicMock()
    network.receive.return_value = None
    monkeypatch.setattr("amazons.model.players.player.msvcrt", FakeMSVCRT())
    monkeypatch.setattr("amazons.model.players.player.time.sleep", lambda _x: None)

    player = NetworkPlayer("Remote", "B", network)

    assert player.get_action(board=None) == "QUIT"
