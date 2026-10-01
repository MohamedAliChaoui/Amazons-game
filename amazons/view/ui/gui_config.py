"""Configuration helpers for the split GTK GUI.

This module contains the configuration-screen logic extracted from the
main GUI window: game mode selection, AI settings, network host/join
parameters, and the transition from configuration to board launch.
"""

import builtins

from amazons.model.board.board import Board
from amazons.model.players.ai_player import AIPlayer
from amazons.model.players.human_player import human_player

from gi.repository import Gtk


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    translator = getattr(builtins, "_", None)
    if translator is None or translator is _:
        return message
    return translator(message)


def setup_config_screen(self):
    """Build the configuration screen and wire its interactive controls."""
    self.set_title(_("Amazons - Game"))
    self.update_menu_visibility(show_game_menu=False)
    self.config_scroll = Gtk.ScrolledWindow()
    self.config_scroll.set_hexpand(True)
    self.config_scroll.set_vexpand(True)
    self.config_scroll.set_policy(
        Gtk.PolicyType.NEVER,
        Gtk.PolicyType.AUTOMATIC,
    )
    self.set_child(self.config_scroll)

    self.main_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL, spacing=15
    )
    self.main_box.set_margin_start(20)
    self.main_box.set_margin_end(20)
    self.main_box.set_margin_top(20)
    self.main_box.set_margin_bottom(20)
    self.config_scroll.set_child(self.main_box)
    title_label = Gtk.Label(label=_("New Game"))
    self.main_box.append(title_label)

    mode_label = Gtk.Label(label=_("Game Mode"))
    mode_label.set_halign(Gtk.Align.START)
    self.mode_combo = Gtk.ComboBoxText()
    self.mode_combo.append("hu", _("Human vs Human"))
    self.mode_combo.append("ai", _("Human vs AI"))
    self.mode_combo.append("aiai", _("AI vs AI"))
    self.mode_combo.append("network", _("Network Game"))
    self.mode_combo.set_active(0)
    self.main_box.append(mode_label)
    self.main_box.append(self.mode_combo)

    self.lbl_board_size = Gtk.Label(label=_("Board Size"))
    self.lbl_board_size.set_halign(Gtk.Align.START)
    self.size_combo = Gtk.ComboBoxText()
    for board_size in range(4, 12):
        size_text = str(board_size)
        self.size_combo.append(size_text, size_text)
    self.size_combo.set_active_id(str(self.size))
    self.main_box.append(self.lbl_board_size)
    self.main_box.append(self.size_combo)

    # --- Names and AI engine selection ---
    self.lbl_name1 = Gtk.Label(label=_("White Player Name"))
    self.lbl_name1.set_halign(Gtk.Align.START)
    self.name1_entry = Gtk.Entry()
    self.name1_entry.set_placeholder_text(_("Enter white player name"))
    self.main_box.append(self.lbl_name1)
    self.main_box.append(self.name1_entry)

    self.lbl_name2 = Gtk.Label(label=_("Black Player Name"))
    self.lbl_name2.set_halign(Gtk.Align.START)
    self.name2_entry = Gtk.Entry()
    self.name2_entry.set_placeholder_text(_("Enter black player name"))
    self.main_box.append(self.lbl_name2)
    self.main_box.append(self.name2_entry)

    self.lbl_ai1 = Gtk.Label(label=_("AI Engine (White)"))
    self.lbl_ai1.add_css_class("config-label")
    self.ai1_combo = Gtk.ComboBoxText()
    self.ai1_combo.append("minimax", "Minimax")
    self.ai1_combo.append("mcts", "MCTS")
    self.ai1_combo.append("random", _("Random"))
    self.ai1_combo.set_active(0)

    self.lbl_ai2 = Gtk.Label(label=_("AI Engine (Black)"))
    self.lbl_ai2.add_css_class("config-label")
    self.ai2_combo = Gtk.ComboBoxText()
    self.ai2_combo.append("minimax", "Minimax")
    self.ai2_combo.append("mcts", "MCTS")
    self.ai2_combo.append("random", _("Random"))
    self.ai2_combo.set_active(0)

    self.lbl_network_role = Gtk.Label(label=_("Network Role"))
    self.lbl_network_role.add_css_class("config-label")
    self.network_role_combo = Gtk.ComboBoxText()
    self.network_role_combo.append("host", _("Host"))
    self.network_role_combo.append("join", _("Join"))
    self.network_role_combo.set_active_id("host")

    self.lbl_network_host = Gtk.Label(label=_("Host / IP Address"))
    self.network_host_entry = Gtk.Entry(text="127.0.0.1")

    self.lbl_network_port = Gtk.Label(label=_("Network Port"))
    self.network_port_entry = Gtk.Entry(text="12345")

    self.network_status_label = Gtk.Label()
    self.network_status_label.set_wrap(True)
    self.network_status_label.set_halign(Gtk.Align.START)

    self.main_box.append(self.lbl_network_role)
    self.main_box.append(self.network_role_combo)
    self.main_box.append(self.lbl_network_host)
    self.main_box.append(self.network_host_entry)
    self.main_box.append(self.lbl_network_port)
    self.main_box.append(self.network_port_entry)
    self.main_box.append(self.network_status_label)

    self.network_actions_box = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=8
    )
    self.btn_network_scan = Gtk.Button(label=_("Scan Servers"))
    self.btn_network_scan.connect("clicked", self.scan_servers_from_gui)
    self.network_actions_box.append(self.btn_network_scan)

    self.btn_network_ping = Gtk.Button(label=_("Ping Server"))
    self.btn_network_ping.connect("clicked", self.ping_server_from_gui)
    self.network_actions_box.append(self.btn_network_ping)

    self.btn_network_status = Gtk.Button(label=_("Network Status"))
    self.btn_network_status.connect(
        "clicked", self.show_network_status_from_gui
    )
    self.network_actions_box.append(self.btn_network_status)

    self.btn_network_stop = Gtk.Button(label=_("Stop Server"))
    self.btn_network_stop.connect(
        "clicked", self.stop_network_server_from_gui
    )
    self.network_actions_box.append(self.btn_network_stop)

    # Add AI controls to the window
    self.main_box.append(self.lbl_ai1)
    self.main_box.append(self.ai1_combo)
    self.main_box.append(self.lbl_ai2)
    self.main_box.append(self.ai2_combo)

    # Show/hide AI and network controls and update default names
    def on_mode_changed(combo):
        mode = combo.get_active_id()
        network_mode = mode == "network"
        join_mode = network_mode and (
            self.network_role_combo.get_active_id() == "join"
        )
        host_lobby_mode = network_mode and not join_mode

        if mode == "hu":
            self.lbl_name1.set_label(_("White Player Name"))
            self.lbl_name2.set_label(_("Black Player Name"))
            self.name1_entry.set_placeholder_text(_("Enter white player name"))
            self.name2_entry.set_placeholder_text(_("Enter black player name"))
        elif mode == "ai":
            self.lbl_name1.set_label(_("White Player Name"))
            self.lbl_name2.set_label(_("Black AI Name"))
            self.name1_entry.set_placeholder_text(_("Enter white player name"))
            self.name2_entry.set_placeholder_text(_("Black AI Name"))
        elif mode == "aiai":
            self.lbl_name1.set_label(_("White AI Name"))
            self.lbl_name2.set_label(_("Black AI Name"))
            self.name1_entry.set_placeholder_text(_("White AI Name"))
            self.name2_entry.set_placeholder_text(_("Black AI Name"))
        else:
            if join_mode:
                self.lbl_name1.set_label(_("Your Name (Black)"))
            else:
                self.lbl_name1.set_label(_("Your Name (White)"))
            self.lbl_name2.set_label(_("Remote Player Name"))
            self.name1_entry.set_placeholder_text(
                _("Enter your player name")
            )
            self.name2_entry.set_placeholder_text(_("Remote Player Name"))

        self.ai1_combo.set_visible(mode == "aiai")
        self.lbl_ai1.set_visible(mode == "aiai")
        self.ai2_combo.set_visible(mode in ("ai", "aiai"))
        self.lbl_ai2.set_visible(mode in ("ai", "aiai"))
        self.lbl_name2.set_visible(not network_mode)
        self.lbl_board_size.set_sensitive(not join_mode)
        self.size_combo.set_sensitive(not join_mode)

        self.lbl_network_role.set_visible(network_mode)
        self.network_role_combo.set_visible(network_mode)
        self.lbl_network_port.set_visible(network_mode)
        self.network_port_entry.set_visible(network_mode)
        self.network_status_label.set_visible(network_mode)
        self.network_actions_box.set_visible(network_mode)

        self.lbl_network_host.set_visible(join_mode)
        self.network_host_entry.set_visible(join_mode)
        self.network_lobby_box.set_visible(host_lobby_mode)

        def is_auto_ai_name(text):
            stripped = text.strip()
            return stripped.startswith("AI_") or not stripped

        if mode == "aiai":
            if is_auto_ai_name(self.name1_entry.get_text()):
                self.name1_entry.set_text(
                    f"AI_{self.ai1_combo.get_active_text()}"
                )
            self.name1_entry.set_sensitive(False)
        elif network_mode:
            self.name1_entry.set_sensitive(True)
        else:
            self.name1_entry.set_sensitive(True)

        if network_mode:
            self.name2_entry.set_sensitive(False)
            self.name2_entry.set_visible(False)
        elif mode in ("ai", "aiai"):
            if is_auto_ai_name(self.name2_entry.get_text()):
                self.name2_entry.set_text(
                    f"AI_{self.ai2_combo.get_active_text()}"
                )
            self.name2_entry.set_sensitive(False)
            self.name2_entry.set_visible(True)
        else:
            self.name2_entry.set_sensitive(True)
            self.name2_entry.set_visible(True)

        if not network_mode:
            self.network_status_label.set_label("")
            self.network_lobby_status_label.set_label("")

        if network_mode:
            if join_mode:
                self.start_btn.set_label(_("Join Server"))
            else:
                self.start_btn.set_label(_("Start Server"))
        else:
            self.start_btn.set_label(_("Start Game"))

        self._update_network_lobby_controls()

    self.mode_combo.connect("changed", on_mode_changed)
    self.network_role_combo.connect(
        "changed", lambda _: on_mode_changed(self.mode_combo)
    )

    # Keep displayed names in sync with AI engine selection.
    self.ai1_combo.connect(
        "changed", lambda _: on_mode_changed(self.mode_combo)
    )
    self.ai2_combo.connect(
        "changed", lambda _: on_mode_changed(self.mode_combo)
    )

    temps_min = str(int(self.controller.time_limit_per_move / 60))
    self.time_entry = Gtk.Entry(text=temps_min)
    self.main_box.append(
        Gtk.Label(
            label=_("Player Time (minutes) - AI thinking: {time}s").format(
                time=self.controller.ai_time
            )
        )
    )
    self.main_box.append(self.time_entry)

    self.start_btn = Gtk.Button(label=_("Start Game"))
    self.start_btn.connect("clicked", self.on_start_game_clicked)
    self.main_box.append(self.start_btn)

    self.main_box.append(self.network_actions_box)

    self.network_lobby_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL, spacing=8
    )
    self.network_lobby_title = Gtk.Label(label=_("Connected Players"))
    self.network_lobby_title.set_halign(Gtk.Align.START)
    self.network_lobby_box.append(self.network_lobby_title)

    self.network_players_scroll = Gtk.ScrolledWindow()
    self.network_players_scroll.set_min_content_height(150)
    self.network_players_scroll.set_policy(
        Gtk.PolicyType.NEVER,
        Gtk.PolicyType.AUTOMATIC,
    )
    self.network_players_list = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=6,
    )
    self.network_players_scroll.set_child(self.network_players_list)
    self.network_lobby_box.append(self.network_players_scroll)

    self.network_lobby_status_label = Gtk.Label()
    self.network_lobby_status_label.set_wrap(True)
    self.network_lobby_status_label.set_halign(Gtk.Align.START)
    self.network_lobby_box.append(self.network_lobby_status_label)

    self.network_lobby_actions_box = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=8
    )
    self.btn_network_refresh_players = Gtk.Button(
        label=_("Refresh Players")
    )
    self.btn_network_refresh_players.connect(
        "clicked",
        self.refresh_network_players_from_gui,
    )
    self.network_lobby_actions_box.append(self.btn_network_refresh_players)

    self.btn_network_invite = Gtk.Button(label=_("Invite Selected Player"))
    self.btn_network_invite.connect(
        "clicked",
        self.invite_selected_player_from_gui,
    )
    self.network_lobby_actions_box.append(self.btn_network_invite)

    self.btn_network_cancel_invite = Gtk.Button(
        label=_("Cancel Invitation")
    )
    self.btn_network_cancel_invite.connect(
        "clicked",
        self.cancel_network_invitation_from_gui,
    )
    self.network_lobby_actions_box.append(self.btn_network_cancel_invite)

    self.btn_network_scoreboard = Gtk.Button(label=_("Show Scoreboard"))
    self.btn_network_scoreboard.connect(
        "clicked",
        self.show_scoreboard_from_gui,
    )
    self.network_lobby_actions_box.append(self.btn_network_scoreboard)
    self.network_lobby_box.append(self.network_lobby_actions_box)

    self.client_match_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL, spacing=8
    )
    self.client_match_title = Gtk.Label(
        label=_("Start a Client Match")
    )
    self.client_match_title.set_halign(Gtk.Align.START)
    self.client_match_box.append(self.client_match_title)

    self.client_match_selection_box = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=8,
    )
    self.client_match_player_one = Gtk.ComboBoxText()
    self.client_match_player_two = Gtk.ComboBoxText()
    self.client_match_selection_box.append(self.client_match_player_one)
    self.client_match_selection_box.append(self.client_match_player_two)
    self.client_match_player_one.connect(
        "changed",
        lambda _combo: self._update_network_lobby_controls(),
    )
    self.client_match_player_two.connect(
        "changed",
        lambda _combo: self._update_network_lobby_controls(),
    )
    self.client_match_box.append(self.client_match_selection_box)

    self.btn_start_client_match = Gtk.Button(
        label=_("Start Client Match")
    )
    self.btn_start_client_match.connect(
        "clicked",
        self.start_client_match_from_gui,
    )
    self.client_match_box.append(self.btn_start_client_match)
    self.network_lobby_box.append(self.client_match_box)
    self.main_box.append(self.network_lobby_box)

    on_mode_changed(self.mode_combo)  # Initialize visibility and names


def on_start_game_clicked(self, btn):
    """Create local players or start the requested network session."""
    mode = self.mode_combo.get_active_id()
    ai1_type = self.ai1_combo.get_active_id()
    ai2_type = self.ai2_combo.get_active_id()
    selected_size = int(self.size_combo.get_active_id() or self.size)

    try:
        t_min = float(self.time_entry.get_text())
    except ValueError:
        t_min = 30.0
    self.controller.time_limit_per_move = t_min * 60
    self.controller.timers = {"W": t_min * 60, "B": t_min * 60}
    n1 = self.name1_entry.get_text().strip() or _("White Player")
    n2 = self.name2_entry.get_text().strip() or _("Black Player")

    if mode == "network":
        role = self.network_role_combo.get_active_id()
        if role == "host":
            self.size = selected_size
            self.controller.size = selected_size
            self.controller.board = Board(selected_size)
            self.controller.history = []
            self.controller.redo_history = []
        host = self.network_host_entry.get_text().strip() or "127.0.0.1"
        try:
            port = int(self.network_port_entry.get_text().strip())
        except ValueError:
            port = 12345
        network_default_name = (
            _("White Player") if role == "host" else _("Black Player")
        )
        self.start_network_from_gui(
            role,
            host,
            port,
            self.name1_entry.get_text().strip() or network_default_name,
        )
        return

    self.size = selected_size
    self.controller.size = selected_size
    self.controller.board = Board(selected_size)
    self.controller.history = []
    self.controller.redo_history = []
    self.controller.is_start_party = True

    if mode == "hu":
        self.controller.players = [
            human_player(n1, "", "W"),
            human_player(n2, "", "B"),
        ]
    elif mode == "ai":
        self.controller.players = [
            human_player(n1, "", "W"),
            AIPlayer(n2, "B", ai_mode=ai2_type),
        ]
    else:
        self.controller.players = [
            AIPlayer(n1, "W", ai_mode=ai1_type),
            AIPlayer(n2, "B", ai_mode=ai2_type),
        ]

    self.launch_game_board()
