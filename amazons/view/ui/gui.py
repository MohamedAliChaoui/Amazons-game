"""GTK main window for the Amazons GUI.

This module contains the live runtime view for the split GUI version:
board rendering, timer updates, drag-and-drop interactions, AI turns,
and network message handling. Configuration and menu callbacks are kept
in dedicated modules to keep this file focused on active game state.
"""

import base64
import builtins
import gi
import time
import threading  # AJOUTÉ pour ne pas bloquer l'interface
import configparser  # AJOUTÉ pour F29
import os  # AJOUTÉ pour F29

from amazons.controller.network.player_text import format_connected_player_line
from amazons.controller.save_load_manager import SaveLoadManager
from amazons.model.board.board import Board
from amazons.model.board.move import Move
from amazons.model.players.ai_player import AIPlayer
from amazons.model.players.human_player import human_player
from amazons.model.players.player import NetworkPlayer
from amazons.view.ui.gui_config import (
    on_start_game_clicked,
    setup_config_screen,
)
from amazons.view.ui.gui_menu import (
    ask_file_path,
    on_config_action,
    on_customize_shortcuts_action,
    on_hint_action,
    on_info_action,
    on_load_game_action,
    on_new_game_action,
    on_pause_action,
    on_redo_action,
    on_save_game_action,
    on_undo_action,
    setup_actions as menu_setup_actions,
    setup_menubar,
    update_menu_visibility,
)
from amazons.view.ui.dialog_utils import show_info_dialog

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk  # noqa: E402


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    translator = getattr(builtins, "_", None)
    if translator is None or translator is _:
        return message
    return translator(message)


# --- AJOUTÉ POUR F29 : Fonction de lecture de la configuration ---
def get_user_shortcut(action_name, default_accel):
    config = configparser.ConfigParser()
    path = os.path.expanduser("~/.amazonsrc")
    if os.path.exists(path):
        try:
            config.read(path)
            if config.has_option("shortcuts", action_name):
                return config.get("shortcuts", action_name)
        except Exception:
            pass
    return default_accel


# --- MODIFIÉ POUR F29 : Liaison dynamique des touches ---
def setup_actions(self):
    """Création des actions et liaison réelle au clavier (F29)"""
    self.window_actions = {}
    actions_list = [
        ("new_game", self.on_new_game_action, "<Control>n"),
        ("save_game", self.on_save_game_action, "<Control>s"),
        ("load_game", self.on_load_game_action, "<Control>l"),
        ("quit", lambda *_: self.close(), "<Control>q"),
        ("undo", self.on_undo_action, "<Control>u"),
        ("redo", self.on_redo_action, "<Control>r"),
        ("pause", self.on_pause_action, "<Control>p"),
        ("hint", self.on_hint_action, "<Control>h"),
        ("info", self.on_info_action, "<Control>i"),
        ("config", self.on_config_action, "<Control>comma"),
        ("customize_shortcuts", self.on_customize_shortcuts_action, None),
    ]

    for name, callback, default_accel in actions_list:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        self.window_actions[name] = action
        
        # On récupère le raccourci depuis .amazonsrc ou on garde le défaut
        if default_accel:
            user_accel = get_user_shortcut(name, default_accel)
            self.app.set_accels_for_action(f"win.{name}", [user_accel])


class ViewGui(Gtk.ApplicationWindow):
    """Main GTK application window for local and network matches."""

    def __init__(self, app, size, controller):
        """Initialize the window and its runtime state."""
        super().__init__(application=app, title=_("Amazons - Game"))
        self.set_default_size(1120, 860)
        self.size = size
        self.controller = controller
        self.app = app

        # États de la machine à états (Gardés intacts)
        self.selected_pos = None
        self.queen_moved_pos = None
        self.waiting_for_arrow = False
        self.game_over = False
        self.paused = False  # Ajouté pour F28/F29

        # AJOUTÉ pour le calcul précis du temps
        self.last_tick_time = time.time()
        self.network_local_name = None
        self.network_remote_name = _("Remote Player")
        self.network_role = None
        self.network_game_started = False
        self.network_polling = False
        self.gui_local_color = None
        self.last_clock_sync_second = None
        self.pending_invitation_dialog = None
        self.pending_invitation_from_id = None
        self.pending_invitation_from_name = None
        self.pending_network_undo_dialog = None
        self.pending_network_undo_requester_color = None
        self.pending_network_undo_requested_at = None
        self.selected_network_player_id = None
        self.network_players_signature = None

        # Widget references set by setup_config_screen / setup_actions
        self.network_players_list = None
        self.client_match_player_one = None
        self.client_match_player_two = None
        self.mode_combo = None
        self.network_role_combo = None
        self.network_lobby_box = None
        self.btn_network_refresh_players = None
        self.btn_network_invite = None
        self.btn_network_cancel_invite = None
        self.btn_network_scoreboard = None
        self.size_combo = None
        self.time_entry = None
        self.start_btn = None

        self.apply_styles()

        # Initialisation des actions et menus (F28 & F29)
        self.setup_actions()
        self.setup_menubar()

        self.setup_config_screen()

    def apply_styles(self):
        """Ton style d'origine enrichi pour les nouvelles fonctions"""
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b"""
            button { font-size: 30px; }
            #light-tile { background: #ffffff; border: 1px solid #ddd; }
            #dark-tile { background: #f6f6f6; border: 1px solid #ddd; }
            #hint-tile { background: #fff9c4; border: 2px solid #fbc02d; }
            #hint-start-tile { background: #c8e6c9; border: 2px solid #4caf50; }
            #hint-end-tile { background: #fff9c4; border: 2px solid #fbc02d; }
            #hint-arrow-tile { background: #ffccbc; border: 2px solid #ff5722; }
            label { font-weight: bold; }
            .config-label { margin-top: 10px; }
        """
        )
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # Les actions de menu et l'écran de configuration sont
    # maintenant définis dans des modules séparés pour alléger
    # ce fichier sans changer leur logique.

    def is_network_game(self):
        """Return ``True`` when one of the current players is remote."""
        return any(
            isinstance(joueur, NetworkPlayer)
            for joueur in self.controller.players
        )

    def _reset_runtime_state(self):
        """Reset transient board interaction state before a new game view."""
        self.selected_pos = None
        self.queen_moved_pos = None
        self.waiting_for_arrow = False
        self.game_over = False
        self.paused = False
        self.last_clock_sync_second = None

    def _set_network_status(self, message):
        """Update the network status label when it exists."""
        if hasattr(self, "network_status_label"):
            self.network_status_label.set_label(message)

    def _set_network_lobby_status(self, message):
        """Update the host-lobby status label when it exists."""
        if hasattr(self, "network_lobby_status_label"):
            self.network_lobby_status_label.set_label(message)

    def _close_pending_invitation_dialog(self):
        """Destroy the current invitation dialog and clear its metadata."""
        dialog = self.pending_invitation_dialog
        self.pending_invitation_dialog = None
        self.pending_invitation_from_id = None
        self.pending_invitation_from_name = None
        if dialog is not None:
            try:
                dialog.destroy()
            except Exception:
                pass

    def _close_pending_network_undo_dialog(self):
        """Destroy the current network undo dialog and clear its state."""
        dialog = self.pending_network_undo_dialog
        self.pending_network_undo_dialog = None
        if dialog is not None:
            try:
                dialog.destroy()
            except Exception:
                pass

    def _clear_pending_network_undo_request(self):
        """Forget the current outgoing network undo request metadata."""
        self.pending_network_undo_requester_color = None
        self.pending_network_undo_requested_at = None

    def _expire_stale_network_undo_request(self):
        """Clear a stuck outgoing network undo request after 30 seconds."""
        requested_at = self.pending_network_undo_requested_at
        if requested_at is None:
            return
        if (time.time() - requested_at) < 30.0:
            return
        self._clear_pending_network_undo_request()
        self._set_network_status(_("Undo request timed out."))
        self.show_message(_("Undo request timed out."))

    def _get_selected_network_player_id(self):
        """Return the selected remote player id from the host lobby."""
        return self.selected_network_player_id

    def _get_network_players_signature(self):
        """Return a stable snapshot of the host lobby content."""
        if not self.controller.server.running:
            return ("stopped",)

        players = self.controller.server.get_players()
        pending = self.controller.server.get_pending_invitations(
            actor_id=self.controller.server.host_player_id
        )
        return (
            tuple(
                (
                    player["id"],
                    player["name"],
                    player["status"],
                    player["address"],
                )
                for player in players
            ),
            tuple(
                (
                    invitation["from_id"],
                    invitation["to_id"],
                    invitation["created_at"],
                )
                for invitation in pending
            ),
        )

    def _set_selected_network_player(self, player_id):
        """Store the selected lobby player and refresh row rendering."""
        self.selected_network_player_id = player_id
        if not hasattr(self, "network_players_list"):
            return

        child = self.network_players_list.get_first_child()
        while child:
            is_selected = getattr(child, "player_id", None) == player_id
            if hasattr(child, "player_text"):
                prefix = "> " if is_selected else ""
                child.set_label(f"{prefix}{child.player_text}")
            child = child.get_next_sibling()

        self._update_network_lobby_controls()

    def _refresh_client_match_choices(self, players):
        """Refresh the host-side selectors used to start client matches."""
        if not hasattr(self, "client_match_player_one"):
            return

        idle_players = [player for player in players if player["status"] == "idle"]
        previous_one = self.client_match_player_one.get_active_id()
        previous_two = self.client_match_player_two.get_active_id()

        self.client_match_player_one.remove_all()
        self.client_match_player_two.remove_all()
        for player in idle_players:
            label = _("{id}: {name}").format(
                id=player["id"],
                name=player["name"],
            )
            self.client_match_player_one.append(player["id"], label)
            self.client_match_player_two.append(player["id"], label)

        if not idle_players:
            return

        idle_ids = [player["id"] for player in idle_players]
        if previous_one in idle_ids:
            self.client_match_player_one.set_active_id(previous_one)
        else:
            self.client_match_player_one.set_active(0)

        if previous_two in idle_ids and previous_two != self.client_match_player_one.get_active_id():
            self.client_match_player_two.set_active_id(previous_two)
        elif len(idle_players) > 1:
            fallback_index = 1 if not self.client_match_player_one.get_active() else 0
            self.client_match_player_two.set_active(fallback_index)
        else:
            self.client_match_player_two.set_active(0)

    def _update_network_lobby_controls(self):
        """Refresh host-lobby button states from the current server state."""
        if not hasattr(self, "network_lobby_box"):
            return

        host_mode = (
            hasattr(self, "mode_combo")
            and self.mode_combo.get_active_id() == "network"
            and self.network_role_combo.get_active_id() == "host"
        )
        server_running = self.controller.server.running
        pending = []
        if server_running:
            pending = self.controller.server.get_pending_invitations(
                actor_id=self.controller.server.host_player_id
            )

        selected_player_id = self._get_selected_network_player_id()
        has_selected_player = selected_player_id is not None
        has_pending_invitation = bool(pending)
        client_match_ready = False
        if hasattr(self, "client_match_player_one"):
            player_one_id = self.client_match_player_one.get_active_id()
            player_two_id = self.client_match_player_two.get_active_id()
            client_match_ready = (
                player_one_id is not None
                and player_two_id is not None
                and player_one_id != player_two_id
            )

        self.network_lobby_box.set_visible(host_mode)
        if not host_mode:
            return

        self.btn_network_refresh_players.set_sensitive(server_running)
        self.btn_network_invite.set_sensitive(
            server_running and has_selected_player and not has_pending_invitation
        )
        self.btn_network_cancel_invite.set_sensitive(
            server_running and has_pending_invitation
        )
        self.btn_network_scoreboard.set_sensitive(server_running)
        if hasattr(self, "btn_start_client_match"):
            self.btn_start_client_match.set_sensitive(
                server_running and client_match_ready and not has_pending_invitation
            )
            self.client_match_player_one.set_sensitive(server_running)
            self.client_match_player_two.set_sensitive(server_running)

        if not server_running:
            self._set_network_lobby_status(
                _("Start the server to manage players.")
            )
            return

        players = self.controller.server.get_players()
        if has_pending_invitation:
            invitation = pending[0]
            self._set_network_lobby_status(
                _("Invitation pending for {player_id} ({name}).").format(
                    player_id=invitation["to_id"],
                    name=invitation["to_name"],
                )
            )
        else:
            self._set_network_lobby_status(
                _("{count} connected player(s).").format(count=len(players))
            )

    def _refresh_network_players_list(self, force=False):
        """Rebuild the host-side player list shown in the lobby."""
        if not hasattr(self, "network_players_list"):
            return

        current_signature = self._get_network_players_signature()
        if not force and current_signature == self.network_players_signature:
            self._update_network_lobby_controls()
            return

        self.network_players_signature = current_signature

        selected_player_id = self._get_selected_network_player_id()
        self.selected_network_player_id = None
        child = self.network_players_list.get_first_child()
        while child:
            self.network_players_list.remove(child)
            child = self.network_players_list.get_first_child()

        if not self.controller.server.running:
            self._refresh_client_match_choices([])
            self._update_network_lobby_controls()
            return

        players = self.controller.server.get_players()
        self._refresh_client_match_choices(players)
        if not players:
            self.network_players_list.append(
                Gtk.Label(label=_("No players connected."), xalign=0.0)
            )
            self._update_network_lobby_controls()
            return

        selected_player_exists = False
        for player in players:
            row_text = format_connected_player_line(player, _)
            player_button = Gtk.Button(label=row_text)
            player_button.player_id = player["id"]
            player_button.player_text = row_text
            player_button.set_halign(Gtk.Align.FILL)
            player_button.set_hexpand(True)
            player_button.connect(
                "clicked",
                lambda _button, player_id=player["id"]: (
                    self._set_selected_network_player(player_id)
                ),
            )
            self.network_players_list.append(player_button)
            if player["id"] == selected_player_id:
                selected_player_exists = True

        if selected_player_exists:
            self._set_selected_network_player(selected_player_id)
        else:
            self._update_network_lobby_controls()

    def _present_invitation_dialog(self, inviter_id, inviter_name):
        """Ask the client-side user whether to accept an invitation."""
        self._close_pending_invitation_dialog()
        self.pending_invitation_from_id = inviter_id
        self.pending_invitation_from_name = inviter_name

        dialog = Gtk.Dialog(
            title=_("Game Invitation"),
            transient_for=self,
            modal=True,
        )
        dialog.add_button(_("Decline"), Gtk.ResponseType.REJECT)
        dialog.add_button(_("Accept"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)

        content_box = dialog.get_content_area()
        content_box.append(
            Gtk.Label(
                label=_(
                    "{name} ({player_id}) invites you to start a network game."
                ).format(name=inviter_name, player_id=inviter_id),
                wrap=True,
            )
        )

        def on_response(current_dialog, response_id):
            if response_id == Gtk.ResponseType.ACCEPT:
                self.controller.client.send("ACCEPT")
                self._set_network_status(
                    _("Invitation accepted. Waiting for the host to start...")
                )
            else:
                self.controller.client.send("DECLINE")
                self._set_network_status(_("Invitation declined."))

            self.pending_invitation_dialog = None
            self.pending_invitation_from_id = None
            self.pending_invitation_from_name = None
            current_dialog.destroy()

        dialog.connect("response", on_response)
        self.pending_invitation_dialog = dialog
        dialog.present()

    def _get_display_name(self, color):
        """Return the visible player name for the given color."""
        if not self.is_network_game():
            return self.controller.players[0 if color == "W" else 1].nom

        if color == self.gui_local_color:
            return self.network_local_name or _("Local Player")
        return self.network_remote_name or _("Remote Player")

    def _send_network_message(self, message):
        """Send one protocol message through the active transport."""
        if self.network_role == "host" and self.controller.server.client_socket:
            return self.controller.server.send(message)
        if self.network_role == "join" and self.controller.client.connected:
            return self.controller.client.send(message)
        return False

    def _refresh_after_undo(self):
        """Reset transient selection state and redraw the current board."""
        self.selected_pos = None
        self.queen_moved_pos = None
        self.waiting_for_arrow = False
        self.refresh_board()
        self.refresh_status_label()

    def _present_network_undo_dialog(self, requester_color):
        """Ask the local player whether the remote undo request is accepted."""
        self._close_pending_network_undo_dialog()
        requester_name = self._get_display_name(requester_color)
        dialog = Gtk.Dialog(
            title=_("Undo Request"),
            transient_for=self,
            modal=True,
        )
        dialog.add_button(_("Decline"), Gtk.ResponseType.REJECT)
        dialog.add_button(_("Accept"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.REJECT)

        content_box = dialog.get_content_area()
        content_box.append(
            Gtk.Label(
                label=_("{name} wants to undo the last round.").format(
                    name=requester_name
                ),
                wrap=True,
            )
        )

        def on_response(current_dialog, response_id):
            self.pending_network_undo_dialog = None
            if response_id == Gtk.ResponseType.ACCEPT:
                if not self._send_network_message("UNDO_OK"):
                    self._set_network_status(
                        _("Failed to acknowledge the undo request.")
                    )
                    self.show_message(
                        _("Failed to acknowledge the undo request.")
                    )
                else:
                    self._set_network_status(
                        _("Undo accepted. Waiting for synchronization.")
                    )
            else:
                if not self._send_network_message("UNDO_NO"):
                    self._set_network_status(
                        _("Failed to decline the undo request.")
                    )
                    self.show_message(
                        _("Failed to decline the undo request.")
                    )
                else:
                    self._set_network_status(_("Undo declined."))
            current_dialog.destroy()

        dialog.connect("response", on_response)
        self.pending_network_undo_dialog = dialog
        dialog.present()

    def _clear_network_message_hooks(self):
        """Remove message callbacks registered on transport objects."""
        self.controller.server.on_message_received = None
        self.controller.client.on_message_received = None

    def _clear_network_buffers(self):
        """Drain queued network messages and clear inbox mirrors."""
        self.controller.server.drain_messages()
        self.controller.client.drain_messages()
        self.controller.server.inbox = []
        self.controller.client.inbox = []

    def _reset_network_session_state(self):
        """Reset GUI metadata associated with a network session."""
        self._close_pending_invitation_dialog()
        self._close_pending_network_undo_dialog()
        self.network_remote_name = _("Remote Player")
        self.network_role = None
        self.network_game_started = False
        self.network_polling = False
        self.gui_local_color = None
        self.last_clock_sync_second = None
        self._clear_pending_network_undo_request()
        self.selected_network_player_id = None
        self.network_players_signature = None

    def _network_session_active(self):
        """Return whether the selected host/client session is still active."""
        if self.network_role == "host":
            return self.controller.server.running
        if self.network_role == "join":
            return self.controller.client.connected
        return False

    def _get_active_network_interface(self):
        """Return the transport object matching the current network role."""
        if self.network_role == "host":
            if self.controller.server.running:
                return self.controller.server
            return None
        if self.network_role == "join" and self.controller.client.connected:
            return self.controller.client
        return None

    def _ensure_network_polling(self):
        """Start the GTK polling loop once for queued network messages."""
        if self.network_polling:
            return
        self.network_polling = True
        GLib.timeout_add(50, self.poll_network_events)
        GLib.idle_add(self.poll_network_events)

    def _initialize_network_game_state(
        self, size, local_color, transport, time_limit
    ):
        """Initialize controller state and players for a network game."""
        self._reset_runtime_state()
        self.size = size
        self.controller.size = size
        self.controller.time_limit_per_move = time_limit
        self.controller.timers = {
            "W": time_limit,
            "B": time_limit,
        }
        self.controller.is_start_party = True
        self.controller.board = Board(size)
        self.controller.history = []
        self.controller.redo_history = []

        remote_name = self.network_remote_name or _("Remote Player")
        if local_color == "W":
            self.controller.players = [
                human_player(self.network_local_name, "", "W"),
                NetworkPlayer(remote_name, "B", transport),
            ]
        else:
            self.controller.players = [
                NetworkPlayer(remote_name, "W", transport),
                human_player(self.network_local_name, "", "B"),
            ]

        self.gui_local_color = local_color
        self.network_game_started = True
        self.last_tick_time = time.time()

    def _start_host_network_game(self):
        """Start the host-side game after the remote client connects."""
        if self.network_game_started or not self.controller.server.client_socket:
            return

        active_player = self.controller.server.get_player(
            self.controller.server.active_player_id
        )
        if active_player:
            self.network_remote_name = active_player["name"]

        time_limit = self.controller.time_limit_per_move
        self._initialize_network_game_state(
            self.size, "W", self.controller.server, time_limit
        )

        start_sent = self.controller.server.send(
            f"START {self.size} WHITE {time_limit:.3f}"
        )
        name_sent = self.controller.server.send(
            f"NAME {self.network_local_name}"
        )
        if not (start_sent and name_sent):
            self.controller.close_network_session(notify_remote=False)
            self._reset_network_session_state()
            self._clear_network_buffers()
            if hasattr(self, "start_btn"):
                self.start_btn.set_sensitive(True)
            self.show_message(
                _("The client disconnected before the game could start.")
            )
            return

        self.launch_game_board()

    def _start_client_network_game(self, message):
        """Initialize the client-side game state from a ``START`` message."""
        if self.network_game_started:
            return

        parts = message.split()
        if len(parts) < 3:
            self.show_message(_("Invalid START message received."))
            return

        try:
            size = int(parts[1])
        except ValueError:
            self.show_message(_("Invalid board size received from host."))
            return

        host_color = parts[2].upper()
        time_limit = self.controller.time_limit_per_move
        if len(parts) >= 4:
            try:
                time_limit = float(parts[3])
            except ValueError:
                pass

        local_color = "B" if host_color == "WHITE" else "W"
        self._initialize_network_game_state(
            size, local_color, self.controller.client, time_limit
        )

        self.controller.client.send(f"NAME {self.network_local_name}")
        self.launch_game_board()

    def _update_timer_labels(self):
        """Refresh both timer labels from the controller timer values."""
        if not hasattr(self, "lbl_white_time"):
            return

        tw, tb = (
            self.controller.timers["W"],
            self.controller.timers["B"],
        )
        self.lbl_white_time.set_label(
            f"{self._get_display_name('W')}: "
            f"{max(0, int(tw // 60)):02d}:{max(0, int(tw % 60)):02d}"
        )
        self.lbl_black_time.set_label(
            f"{self._get_display_name('B')}: "
            f"{max(0, int(tb // 60)):02d}:{max(0, int(tb % 60)):02d}"
        )

    def _apply_remote_clock_update(self, color, remaining):
        """Apply a clock snapshot received from the remote player."""
        if color not in ("W", "B"):
            return

        try:
            remaining_value = max(0.0, float(remaining))
        except (TypeError, ValueError):
            return

        self.controller.timers[color] = remaining_value
        self._update_timer_labels()

    def _sync_clock_snapshot(self, color=None, force=False):
        """Send the local remaining time to the connected peer."""
        if not self.is_network_game() or not self.gui_local_color:
            return

        color = color or self.gui_local_color
        if color != self.gui_local_color:
            return

        remaining = max(0.0, self.controller.timers[color])
        remaining_second = int(remaining)
        if not force and self.last_clock_sync_second == remaining_second:
            return

        self.last_clock_sync_second = remaining_second
        self._send_network_message(f"CLOCK {color} {remaining:.3f}")

    def _record_hosted_network_result(self, winner_color):
        """Update the host-side scoreboard after one completed GUI game."""
        if self.network_role != "host":
            return False
        if self.controller.server.host_player["status"] != "ingame":
            return False
        if not self.controller.server.active_player_id:
            return False

        host_result = "win" if winner_color == "W" else "loss"
        remote_result = "loss" if host_result == "win" else "win"
        self.controller.server.record_completed_game(
            host_result,
            remote_result,
            player_id=self.controller.server.active_player_id,
        )
        self._refresh_network_players_list()
        return True

    def _send_network_game_over(self, winner_color, reason):
        """Broadcast a structured game-over notification to the peer."""
        if not self.is_network_game():
            return
        self._send_network_message(f"GAMEOVER WINNER={winner_color} {reason}")

    def _parse_network_game_over(self, message):
        """Extract the winner color and user-facing text from a GAMEOVER."""
        payload = message[9:].strip()
        winner_color = None
        display_message = payload

        if payload.upper().startswith("WINNER="):
            parts = payload.split(maxsplit=1)
            winner_token = parts[0].split("=", 1)[1].upper()
            if winner_token in ("W", "B"):
                winner_color = winner_token
            if len(parts) > 1:
                display_message = parts[1]

        return winner_color, display_message

    def _finish_network_game(self, winner_color=None, status_message=None):
        """Finalize the current network match without closing the transport."""
        if self.network_role == "host" and winner_color in ("W", "B"):
            self._record_hosted_network_result(winner_color)

        self.network_game_started = False
        if status_message:
            self._set_network_status(status_message)
        if self.network_role == "host":
            self._refresh_network_players_list()

    def _close_join_network_session(self, message):
        """Close the client-side session after a remote shutdown."""
        self.network_game_started = False
        self.controller.close_network_session(notify_remote=False)
        self._clear_network_message_hooks()
        self._clear_network_buffers()
        self._reset_network_session_state()
        self.network_polling = False
        self.show_message(message)

    def _format_network_status(self):
        """Build a human-readable summary of current network state."""
        lines = [
            _("Server running: {value}").format(
                value=self.controller.server.running
            ),
            _("Client connected: {value}").format(
                value=self.controller.client.connected
            ),
        ]
        if self.controller.server.running:
            server_status = self.controller.server.get_status()
            lines.append(
                _("Client connected to server: {value}").format(
                    value=bool(self.controller.server.client_socket)
                )
            )
            lines.append(
                _("Connected clients: {count}").format(
                    count=server_status["connected_clients"]
                )
            )
            lines.append(
                _("Parties in progress: {count}").format(
                    count=server_status["parties_in_progress"]
                )
            )
            lines.append(
                _("Active player: {player_id}").format(
                    player_id=server_status["active_player_id"] or "-"
                )
            )
        if self.controller.client.connected:
            lines.append(
                _("Remote server: {host}:{port}").format(
                    host=self.controller.client.host,
                    port=self.controller.client.port,
                )
            )
        return "\n".join(lines)

    def scan_servers_from_gui(self, *args):
        """Scan the LAN for servers without blocking the GTK main loop."""
        self._set_network_status(_("Scanning local network for servers..."))

        def worker():
            deadline = time.time() + 4.0
            servers = []
            while time.time() < deadline:
                servers = self.controller.discovery.get_server_list()
                if servers:
                    break
                time.sleep(0.2)

            def update_ui():
                if not servers:
                    self._set_network_status(
                        _("No servers found on the local network.")
                    )
                    self.show_message(
                        _("No servers found on the local network.")
                    )
                    return False

                first = servers[0]
                if hasattr(self, "network_host_entry"):
                    self.network_host_entry.set_text(first["ip"])
                if hasattr(self, "network_port_entry"):
                    self.network_port_entry.set_text(str(first["port"]))

                lines = [
                    f"- {srv['name']} : {srv['ip']}:{srv['port']}"
                    for srv in servers
                ]
                self._set_network_status(
                    _("{count} server(s) found.").format(
                        count=len(servers)
                    )
                )
                self.show_message(
                    _("Available Servers:") + "\n\n" + "\n".join(lines)
                )
                return False

            GLib.idle_add(update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def ping_server_from_gui(self, *args):
        """Measure latency to the connected server asynchronously."""
        self._set_network_status(_("Ping in progress..."))

        def worker():
            message = self.controller.client.ping()

            def update_ui():
                self._set_network_status(message)
                self.show_message(message)
                return False

            GLib.idle_add(update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def show_network_status_from_gui(self, *args):
        """Show the current network transport state in a dialog."""
        message = self._format_network_status()
        self._set_network_status(message)
        self.show_message(message)

    def refresh_network_players_from_gui(self, *args):
        """Refresh the host-side lobby list of connected players."""
        if not self.controller.server.running:
            self.show_message(_("Start the server before listing players."))
            return
        self._refresh_network_players_list()

    def invite_selected_player_from_gui(self, *args):
        """Invite the selected lobby player to start a hosted game."""
        if not self.controller.server.running:
            self.show_message(_("Start the server before sending invitations."))
            return

        player_id = self._get_selected_network_player_id()
        if not player_id:
            self.show_message(_("Select one connected player first."))
            return

        result = self.controller.server.request_invitation(
            self.controller.server.host_player_id,
            player_id,
        )
        self._handle_network_message(result)
        self._refresh_network_players_list()

    def cancel_network_invitation_from_gui(self, *args):
        """Cancel the host's current outgoing invitation."""
        if not self.controller.server.running:
            self.show_message(_("The server is not running."))
            return

        result = self.controller.server.cancel_invitation(
            self.controller.server.host_player_id
        )
        self._handle_network_message(result)
        self._refresh_network_players_list()

    def show_scoreboard_from_gui(self, *args):
        """Display the current host-side scoreboard in a dialog."""
        if not self.controller.server.running:
            self.show_message(_("Start the server to access the scoreboard."))
            return

        entries = self.controller.server.get_scoreboard()
        if not entries:
            self.show_message(_("Scoreboard is empty."))
            return

        lines = [
            _("{name}: {wins} win(s), {losses} loss(es), {played} game(s)").format(
                name=entry["name"],
                wins=entry["wins"],
                losses=entry["losses"],
                played=entry["played"],
            )
            for entry in entries
        ]
        self.show_message(_("Scoreboard") + "\n\n" + "\n".join(lines))

    def start_client_match_from_gui(self, *args):
        """Start a server-relayed game between two connected clients."""
        if not self.controller.server.running:
            self.show_message(_("Start the server before pairing clients."))
            return

        player_one_id = self.client_match_player_one.get_active_id()
        player_two_id = self.client_match_player_two.get_active_id()
        if not player_one_id or not player_two_id:
            self.show_message(_("Select two clients first."))
            return
        if player_one_id == player_two_id:
            self.show_message(_("Select two different clients."))
            return

        try:
            board_size = int(self.size_combo.get_active_id() or self.size)
        except (TypeError, ValueError):
            board_size = self.size

        try:
            time_limit = float(self.time_entry.get_text()) * 60.0
        except ValueError:
            time_limit = self.controller.time_limit_per_move

        self.controller.server.default_board_size = board_size
        self.controller.server.default_time_limit = time_limit
        result = self.controller.server.start_client_match(
            player_one_id,
            player_two_id,
            size=board_size,
            time_limit=time_limit,
        )
        if result.startswith("ERROR"):
            self.show_message(result)
        else:
            self._set_network_lobby_status(
                _("Started a client match between {player_one} and {player_two}.").format(
                    player_one=player_one_id,
                    player_two=player_two_id,
                )
            )
        self._refresh_network_players_list(force=True)

    def stop_network_server_from_gui(self, *args):
        """Stop the host transport and reset GUI-side network state."""
        self.controller.server.stop()
        self._clear_network_message_hooks()
        self._clear_network_buffers()
        self._reset_network_session_state()
        self._set_network_status(_("Server stopped."))
        self._set_network_lobby_status(_("Server stopped."))
        self._refresh_network_players_list()
        if hasattr(self, "start_btn"):
            self.start_btn.set_sensitive(True)

    def start_network_from_gui(self, role, host, port, local_name):
        """Host or join a network game from the configuration screen."""
        local_name = local_name.strip() or _("Local Player")
        self.controller.close_network_session(notify_remote=False)
        self._clear_network_message_hooks()
        self._clear_network_buffers()
        self._reset_network_session_state()
        self.start_btn.set_sensitive(False)
        self.network_local_name = local_name
        self.network_role = role

        if role == "host":
            self.controller.server.server_name = local_name
            self.controller.server.default_board_size = self.size
            self.controller.server.default_time_limit = self.controller.time_limit_per_move
            error = self.controller.server.start(port)
            if error:
                self.start_btn.set_sensitive(True)
                self.show_message(error)
                return

            self.controller.server.set_host_player(local_name, status="idle")

            self._set_network_status(
                _("Server started on port {port}. Waiting for a client...").format(
                    port=port
                )
            )
            self._refresh_network_players_list()
            self._ensure_network_polling()
            return

        error = self.controller.client.join(host, port)
        if error:
            self.start_btn.set_sensitive(True)
            self.show_message(error)
            return

        self.controller.client.send(f"NAME {local_name}")

        self._set_network_status(
            _("Connected to {host}:{port}. Waiting for the host to start...").format(
                host=host,
                port=port,
            )
        )
        self._ensure_network_polling()

    def _wait_for_network_client_gui(self):
        """Compatibility wrapper that delegates to the unified poller."""
        return self.poll_network_events()

    def _wait_for_network_start_gui(self):
        """Compatibility wrapper that delegates to the unified poller."""
        return self.poll_network_events()

    def _update_remote_player_name(self, name):
        """Update the remote player name across labels and player objects."""
        if not name:
            return
        self.network_remote_name = name
        for joueur in self.controller.players:
            if isinstance(joueur, NetworkPlayer):
                joueur.nom = name
                break
        self._update_timer_labels()
        if hasattr(self, "lbl_status") and not self.game_over:
            self.refresh_status_label()

    def _apply_remote_loaded_game(self, encoded_payload):
        """Load and apply a save file received from the remote host."""
        try:
            raw_content = base64.b64decode(encoded_payload).decode("utf-8")
        except Exception:
            self.show_message(_("Invalid network save received."))
            return

        success, message = SaveLoadManager.load_game_from_text(
            self.controller, raw_content
        )
        if not success:
            self.show_message(message)
            return

        self.size = self.controller.size
        self.controller.is_start_party = True
        self.controller.is_saved = True
        self._reset_runtime_state()
        self.last_tick_time = time.time()
        self.refresh_board()
        self._update_timer_labels()
        if not self.check_game_over():
            self.refresh_status_label()
        self._set_network_status(_("Game synchronized with the host."))

    def sync_loaded_game_to_remote(self, filepath):
        """Send a loaded save file to the connected remote client."""
        if not self.controller.server.client_socket:
            return True

        success, raw_content = SaveLoadManager.read_text_file(filepath)
        if not success:
            self.show_message(
                _("Failed to read file for synchronization: {error}").format(
                    error=raw_content
                )
            )
            return False

        payload = base64.b64encode(raw_content.encode("utf-8")).decode("ascii")
        return self.controller.server.send(f"LOAD_STATE {payload}")

    def _apply_remote_move_notation(self, notation):
        """Parse and apply a move notation received over the network."""
        move_text = notation.strip()
        color = "W" if not len(self.controller.history) % 2 else "B"
        if move_text and move_text[0] in ("W", "B"):
            color = move_text[0]
            move_text = move_text[1:]

        try:
            path_text, arrow_text = move_text.split("/")
            start_text, end_text = path_text.split("-")
            move = Move(
                Move.from_algebraic(start_text, self.size),
                Move.from_algebraic(end_text, self.size),
                Move.from_algebraic(arrow_text, self.size),
            )
            self.controller.board.make_move(move, color)
        except Exception:
            self.show_message(_("Invalid network move received."))
            return

        self.controller.history.append((move, color))
        self.controller.redo_history.clear()
        self.selected_pos = None
        self.waiting_for_arrow = False
        self.refresh_board()
        if not self.check_game_over():
            self.refresh_status_label()

    def _sync_last_move_if_network(self):
        """Transmit the last local move to the remote peer."""
        if not self.is_network_game() or not self.controller.history:
            return

        move, color = self.controller.history[-1]
        start_text = Move.to_algebraic(move.start_pos, self.size)
        end_text = Move.to_algebraic(move.end_pos, self.size)
        arrow_text = Move.to_algebraic(move.arrow_pos, self.size)
        self._send_network_message(
            f"MOVE {color}{start_text}-{end_text}/{arrow_text}"
        )

    def _handle_network_message(self, message):
        """Dispatch one network message to the appropriate GUI action."""
        msg_upper = message.upper()

        if msg_upper.startswith("START "):
            self._start_client_network_game(message)
            return

        if msg_upper.startswith("HOST_START_GAME "):
            parts = message.split(maxsplit=1)
            if len(parts) == 2:
                self.controller.server.set_active_player(parts[1].strip())
            self._set_network_status(
                _("Invitation accepted. Starting the game...")
            )
            self._start_host_network_game()
            return

        if msg_upper.startswith("INVITE_FROM "):
            parts = message.split(maxsplit=2)
            inviter_id = parts[1] if len(parts) >= 2 else "HOST"
            inviter_name = parts[2] if len(parts) >= 3 else _("Host")
            self._set_network_status(
                _("Invitation received from {name} ({player_id}).").format(
                    name=inviter_name,
                    player_id=inviter_id,
                )
            )
            self._present_invitation_dialog(inviter_id, inviter_name)
            return

        if msg_upper.startswith("INVITE_SENT "):
            parts = message.split(maxsplit=2)
            if len(parts) >= 3:
                self._set_network_status(
                    _("Invitation sent to {name} ({player_id}).").format(
                        name=parts[2],
                        player_id=parts[1],
                    )
                )
            self._refresh_network_players_list()
            return

        if msg_upper.startswith("INVITE_ACCEPTED "):
            parts = message.split(maxsplit=2)
            if len(parts) >= 3:
                self._set_network_status(
                    _("Invitation accepted by {name} ({player_id}).").format(
                        name=parts[2],
                        player_id=parts[1],
                    )
                )
            self._close_pending_invitation_dialog()
            self._refresh_network_players_list()
            return

        if msg_upper.startswith("INVITE_DECLINED "):
            parts = message.split(maxsplit=2)
            if len(parts) >= 3:
                self._set_network_status(
                    _("Invitation declined by {name} ({player_id}).").format(
                        name=parts[2],
                        player_id=parts[1],
                    )
                )
            self._close_pending_invitation_dialog()
            self._refresh_network_players_list()
            return

        if msg_upper.startswith("INVITE_CANCELLED "):
            parts = message.split(maxsplit=2)
            if len(parts) >= 3:
                self._set_network_status(
                    _("Invitation cancelled by {name} ({player_id}).").format(
                        name=parts[2],
                        player_id=parts[1],
                    )
                )
            self._close_pending_invitation_dialog()
            self._refresh_network_players_list()
            return

        if msg_upper.startswith("INVITE_EXPIRED "):
            parts = message.split(maxsplit=2)
            if len(parts) >= 3:
                self._set_network_status(
                    _("Invitation expired with {name} ({player_id}).").format(
                        name=parts[2],
                        player_id=parts[1],
                    )
                )
            self._close_pending_invitation_dialog()
            self._refresh_network_players_list()
            return

        if msg_upper.startswith("ERROR "):
            self._set_network_status(message)
            self.show_message(message)
            self._refresh_network_players_list()
            return

        if msg_upper.startswith("NAME "):
            self._update_remote_player_name(message[5:].strip())
            return

        if msg_upper.startswith("CLOCK "):
            parts = message.split(maxsplit=2)
            if len(parts) == 3:
                self._apply_remote_clock_update(parts[1], parts[2])
            return

        if msg_upper.startswith("MOVE "):
            if self.network_game_started:
                self._apply_remote_move_notation(message[5:].strip())
            return

        if msg_upper == "SERVER_STOP":
            self.game_over = True
            self._close_join_network_session(
                _("The host stopped the server and closed the session.")
            )
            return

        if msg_upper == "TIMEOUT":
            self.game_over = True
            self._close_join_network_session(
                _("The network session expired after inactivity.")
            )
            return

        if msg_upper in ("QUIT", "QUIT_GAME"):
            self.game_over = True
            leave_message = _("The remote player left the game.")
            if self.network_role == "host":
                self._finish_network_game(
                    winner_color="W",
                    status_message=leave_message,
                )
                self.show_message(leave_message)
                return

            self._close_join_network_session(leave_message)
            return

        if msg_upper.startswith("GAMEOVER "):
            if self.game_over and not self.network_game_started:
                return
            self.game_over = True
            winner_color, display_message = self._parse_network_game_over(
                message
            )
            self.lbl_status.set_markup(
                "<span foreground='#e67e22' size='large'>"
                f"<b>{GLib.markup_escape_text(display_message)}</b>"
                "</span>"
            )
            self._finish_network_game(
                winner_color=winner_color,
                status_message=display_message,
            )
            self.show_message(display_message)
            return

        if msg_upper.startswith("UNDO_REQ"):
            parts = message.split(maxsplit=1)
            requester_color = parts[1].strip().upper() if len(parts) == 2 else None
            self._set_network_status(_("Remote player requested an undo."))
            self._present_network_undo_dialog(requester_color)
            return

        if msg_upper == "UNDO_OK":
            requester_color = self.pending_network_undo_requester_color
            self._clear_pending_network_undo_request()
            if (
                requester_color
                and self.network_role == "host"
                and self.controller.server.client_socket
            ):
                self.controller.apply_undo_batch(
                    requester_color, announce=False
                )
                self._refresh_after_undo()
                if self.controller.sync_current_state_to_remote():
                    self._set_network_status(
                        _("Undo accepted. Game synchronized.")
                    )
                else:
                    self._set_network_status(
                        _("Undo applied locally, but synchronization failed.")
                    )
                    self.show_message(
                        _("Undo applied locally, but synchronization failed.")
                    )
            else:
                self._set_network_status(
                    _("Undo accepted. Waiting for synchronized game state.")
                )
            return

        if msg_upper == "UNDO_NO":
            self._clear_pending_network_undo_request()
            self._set_network_status(_("Undo declined by the remote player."))
            self.show_message(_("Undo declined by the remote player."))
            return

        if msg_upper.startswith("LOAD_STATE "):
            self._clear_pending_network_undo_request()
            self._apply_remote_loaded_game(message[11:].strip())
            return

    def poll_network_events(self):
        """Poll and process queued network messages from the main thread."""
        self._expire_stale_network_undo_request()
        if not self._network_session_active():
            if hasattr(self, "start_btn") and not self.network_game_started:
                self.start_btn.set_sensitive(True)
            self.network_polling = False
            return False

        if self.network_role == "host" and not self.network_game_started:
            self._refresh_network_players_list()
            if not self.controller.server.get_players():
                self._set_network_status(
                    _("Server started. Waiting for a client...")
                )

        if (
            self.network_role == "host"
            and self.network_game_started
            and not self.game_over
            and self.controller.server.host_player["status"] != "ingame"
        ):
            self.game_over = True
            self.network_game_started = False
            disconnect_message = _(
                "The remote player disconnected. The hosted game ended."
            )
            self._set_network_status(disconnect_message)
            self._refresh_network_players_list()
            self.show_message(disconnect_message)
            self.network_polling = False
            return False

        interface = self._get_active_network_interface()
        if interface is None:
            return True

        for message in interface.drain_messages():
            self._handle_network_message(message)
            if self.game_over or not self._network_session_active():
                self.network_polling = False
                return False

        return True

    def launch_game_board(self):
        """Switch the window from configuration to the live game board."""
        self.set_title(_("Amazons - Game"))
        self.update_menu_visibility(show_game_menu=True)
        self.set_child(None)
        self.main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0
        )
        self.set_child(self.main_box)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        toolbar.set_margin_start(10)
        toolbar.set_margin_top(5)
        toolbar.set_margin_bottom(5)

        self.info_box = Gtk.CenterBox()
        self.info_box.set_margin_top(10)
        self.info_box.set_margin_bottom(10)
        self.lbl_white_time = Gtk.Label()
        self.lbl_status = Gtk.Label(label=_("Turn: White"))
        self.lbl_black_time = Gtk.Label()
        self.info_box.set_start_widget(self.lbl_white_time)
        self.info_box.set_center_widget(self.lbl_status)
        self.info_box.set_end_widget(self.lbl_black_time)
        self.main_box.append(self.info_box)

        self.grid = Gtk.Grid()
        self.grid.set_halign(Gtk.Align.CENTER)
        self.main_box.append(self.grid)

        self.refresh_board()
        self.refresh_status_label()
        self._update_timer_labels()

        self.last_tick_time = time.time()  # Reset le temps au lancement
        GLib.timeout_add(100, self.update_timers)
        self.check_game_over()
        GLib.timeout_add(500, self.check_ai_turn)
        if self.is_network_game():
            self._ensure_network_polling()
        else:
            self._clear_network_message_hooks()

    def on_undo_clicked(self, btn):
        """Handle an undo request from the current local player."""
        if self.game_over:
            return
        idx = len(self.controller.history) % 2
        if self.is_network_game() and self.gui_local_color in ("W", "B"):
            local_idx = 0 if self.gui_local_color == "W" else 1
            joueur_demandeur = self.controller.players[local_idx]
            adversaire = self.controller.players[1 - local_idx]
        else:
            joueur_demandeur = self.controller.players[idx]
            adversaire = self.controller.players[1 - idx]

        can_undo, message = self.controller.can_undo_for_player(
            joueur_demandeur
        )
        if not can_undo:
            self.show_message(message)
            return

        from amazons.model.players.ai_player import AIPlayer
        if isinstance(adversaire, AIPlayer):
            if self.controller.undo_turn(joueur_demandeur, adversaire):
                self._refresh_after_undo()
            return

        if self.is_network_game() and isinstance(adversaire, NetworkPlayer):
            self._expire_stale_network_undo_request()
            if self.pending_network_undo_requester_color is not None:
                self.show_message(_("An undo request is already pending."))
                return
            if not self._send_network_message(
                f"UNDO_REQ {joueur_demandeur.color_code}"
            ):
                self._set_network_status(_("Failed to send undo request."))
                self.show_message(_("Failed to send undo request."))
                return
            self.pending_network_undo_requester_color = (
                joueur_demandeur.color_code
            )
            self.pending_network_undo_requested_at = time.time()
            self._set_network_status(
                _("Waiting for the remote player to answer the undo request.")
            )
            return

        dialog = Gtk.Dialog(
            title=_("Undo Request"),
            transient_for=self,
            modal=True,
        )
        dialog.add_button(_("Yes"), Gtk.ResponseType.YES)
        dialog.add_button(_("No"), Gtk.ResponseType.NO)
        dialog.set_default_response(Gtk.ResponseType.NO)
        
        content_box = dialog.get_content_area()
        label = Gtk.Label(
            label=_("{name}, do you agree to undo the last round?").format(
                name=adversaire.nom
            )
        )
        label.set_wrap(True)
        content_box.append(label)
        dialog.present()
        
        # Use callback to handle response
        def on_undo_response(dialog, response_id):
            if response_id == Gtk.ResponseType.YES:
                self.controller.apply_undo_batch(
                    joueur_demandeur.color_code,
                    announce=False,
                )
                self._refresh_after_undo()
            dialog.destroy()

        dialog.connect("response", on_undo_response)

    def refresh_status_label(self):
        """Refresh the status label with the side currently to move."""
        current_color = (
            "W" if not len(self.controller.history) % 2 else "B"
        )
        joueur_nom = self._get_display_name(current_color)
        suffix = ""
        if self.is_network_game() and current_color != self.gui_local_color:
            suffix = _(" (remote)")
        self.lbl_status.set_label(
            _("Turn: {name}{suffix}").format(name=joueur_nom, suffix=suffix)
        )

    def update_timers(self):
        """Advance the active timer and refresh the visible clocks."""
        if self.game_over or self.paused:
            self.last_tick_time = (
                time.time()
            )  # Reset pour ne pas compter la pause
            return True

        now = time.time()
        elapsed = now - self.last_tick_time
        self.last_tick_time = now

        current_idx = len(self.controller.history) % 2
        color_key = "W" if not current_idx else "B"

        if self.is_network_game() and color_key != self.gui_local_color:
            self._update_timer_labels()
            return True

        self.controller.timers[color_key] -= elapsed
        if self.controller.timers[color_key] < 0:
            self.controller.timers[color_key] = 0

        self._update_timer_labels()
        self._sync_clock_snapshot(color_key)

        if self.controller.timers[color_key] <= 0:
            self.game_over = True
            winner_color = "B" if not current_idx else "W"
            winner = self._get_display_name(winner_color)
            self._sync_clock_snapshot(color_key, force=True)
            timeout_message = _("TIME OUT! {winner} wins.").format(
                winner=winner
            )
            if self.is_network_game():
                self._send_network_game_over(
                    winner_color,
                    _("Time out."),
                )
                self._finish_network_game(
                    winner_color=winner_color,
                    status_message=timeout_message,
                )
            self.lbl_status.set_markup(
                "<span foreground='#c0392b'>"
                f"{GLib.markup_escape_text(timeout_message)}"
                "</span>"
            )
            return False
        return True

    def refresh_board(self, highlights=None, hints=None):
        """Redraw the board and optionally highlight legal target cells."""
        child = self.grid.get_first_child()
        while child:
            self.grid.remove(child)
            child = self.grid.get_first_child()
        board_data = self.controller.board.get_board_array()
        for r in range(self.size):
            for c in range(self.size):
                btn = Gtk.Button(label=self.get_icon(board_data[r][c]))
                btn.set_size_request(60, 60)
                btn.set_name("light-tile" if not (r + c) % 2 else "dark-tile")
                if highlights and (r, c) in highlights:
                    btn.set_label("·")
                if hints and (r, c) in hints:
                    btn.set_name(hints[(r, c)])

                btn.connect("clicked", self.on_tile_clicked, r, c)

                # --- DRAG AND DROP (F30) ---
                if board_data[r][c] in ("W", "B"):
                    drag_source = Gtk.DragSource.new()
                    drag_source.set_actions(Gdk.DragAction.MOVE)
                    # Lambda pour filtrer les arguments prepare
                    drag_source.connect(
                        "prepare",
                        lambda src, x, y, row=r, col=c: self.on_drag_prepare(
                            src, row, col
                        ),
                    )
                    btn.add_controller(drag_source)

                drop_target = Gtk.DropTarget.new(
                    GObject.TYPE_STRING, Gdk.DragAction.MOVE
                )
                drop_target.set_gtypes([GObject.TYPE_STRING])
                # Lambda pour filtrer les arguments drop (ignore x, y)
                def handle_drop(target, value, x, y, row=r, col=c):
                    return self.on_drop_received(
                        target, value, row, col
                    )

                drop_target.connect("drop", handle_drop)
                btn.add_controller(drop_target)

                self.grid.attach(btn, c, r, 1, 1)

    def on_drag_prepare(self, source, r, c):
        """Prepare drag data for a queen that is currently movable."""
        if self.game_over or self.paused or self.waiting_for_arrow:
            return None
        idx = len(self.controller.history) % 2
        current_color = "W" if not idx else "B"
        if isinstance(self.controller.players[idx], AIPlayer):
            return None
        if self.is_network_game() and current_color != self.gui_local_color:
            return None
        return Gdk.ContentProvider.new_for_value(f"{r},{c}")

    def on_drop_received(self, target, value, r, c):
        """Translate a drop action into the corresponding board click."""
        try:
            start_r, start_c = map(int, value.split(","))
            self.selected_pos = start_r * self.size + start_c
            self.on_tile_clicked(None, r, c)
            return True
        except Exception:
            return False

    def get_icon(self, value):
        """Return the Unicode symbol used for a board cell value."""
        return {"W": "♕", "B": "♛", "X": "✘"}.get(value, "")

    def on_tile_clicked(self, btn, r, c):
        """Handle the local player's two-step queen move and arrow shot."""
        if self.game_over or self.paused:
            return
        idx = len(self.controller.history) % 2
        current_color = "W" if not idx else "B"
        if isinstance(self.controller.players[idx], AIPlayer):
            return
        if self.is_network_game() and current_color != self.gui_local_color:
            return
        pos, color = r * self.size + c, "W" if not idx else "B"

        if self.selected_pos is None:
            bb = (
                self.controller.board.white_bb
                if not idx
                else self.controller.board.black_bb
            )
            if (bb >> pos) & 1:
                self.selected_pos = pos
                t = list(
                    self.controller.board.get_queen_moves_iterator(
                        pos, self.controller.board.occupied()
                    )
                )
                self.refresh_board(
                    highlights=[(p // self.size, p % self.size) for p in t]
                )
        elif not self.waiting_for_arrow:
            if (
                self.controller.board.is_valid_queen_move(
                    self.selected_pos, pos, color
                )
                is True
            ):
                self.controller.board.move_queen(self.selected_pos, pos, color)
                self.queen_moved_pos, self.waiting_for_arrow = pos, True
                t = list(
                    self.controller.board.get_queen_moves_iterator(
                        pos, self.controller.board.occupied()
                    )
                )
                self.refresh_board(
                    highlights=[(p // self.size, p % self.size) for p in t]
                )
            else:
                self.selected_pos = None
                self.refresh_board()
        else:
            if (
                self.controller.board.is_valid_arrow_shot(
                    self.queen_moved_pos, pos
                )
                is True
            ):
                self.controller.board.place_arrow(pos)
                self.controller.history.append(
                    (Move(self.selected_pos, self.queen_moved_pos, pos), color)
                )
                self.controller.redo_history.clear()
                self._sync_clock_snapshot(current_color, force=True)
                self._sync_last_move_if_network()
                self.selected_pos = None
                self.waiting_for_arrow = False
                self.refresh_board()
                if not self.check_game_over():
                    self.refresh_status_label()
                    GLib.timeout_add(500, self.check_ai_turn)

    def check_ai_turn(self):
        """Start asynchronous AI thinking when it is an AI turn."""
        if self.game_over or self.paused:
            return False
        idx = len(self.controller.history) % 2
        joueur = self.controller.players[idx]

        if isinstance(joueur, AIPlayer):
            self.lbl_status.set_label(
                _("Thinking: {name}...").format(name=joueur.nom)
            )
            def ai_worker():
                move = joueur.get_action(
                    self.controller.board, time_limit=self.controller.ai_time
                )
                GLib.idle_add(self.apply_ai_move, move, idx)

            threading.Thread(target=ai_worker, daemon=True).start()

        return False

    def apply_ai_move(self, move, idx):
        """Apply the move produced by the background AI worker."""
        if move and not self.game_over:
            color = "W" if not idx else "B"
            self.controller.board.make_move(move, color)
            self.controller.history.append((move, color))
            self.refresh_board()

            if not self.check_game_over():
                self.refresh_status_label()
                GLib.timeout_add(500, self.check_ai_turn)
        elif not move:
            self.game_over = True
            self.lbl_status.set_label(
                _("{name} resigns!").format(
                    name=self.controller.players[idx].nom
                )
            )
        return False

    def check_game_over(self):
        """Check whether the side to move has any legal move left."""
        color_to_check = "W" if not len(self.controller.history) % 2 else "B"
        if not self.controller.board.has_moves(color_to_check):
            self.game_over = True
            winner_color = "B" if color_to_check == "W" else "W"
            winner_name = self._get_display_name(winner_color)
            victory_message = _("VICTORY: {winner}!").format(
                winner=winner_name
            )
            if self.is_network_game():
                self._send_network_game_over(
                    winner_color,
                    _("No legal moves remain."),
                )
                self._finish_network_game(
                    winner_color=winner_color,
                    status_message=victory_message,
                )
            self.lbl_status.set_markup(
                "<span foreground='#e67e22' size='large'>"
                f"<b>{GLib.markup_escape_text(victory_message)}</b>"
                "</span>"
            )
            GLib.idle_add(self.show_winner_dialog, winner_name)
            return True
        return False

    def show_message(self, message):
        show_info_dialog(self, Gtk, message)

    def show_winner_dialog(self, name):
        """Show a modal dialog announcing the winner."""
        show_info_dialog(
            self,
            Gtk,
            _("GAME OVER\n\nPlayer {name} wins!").format(name=name),
        )

    def setup_shortcuts(self):
        """Reserved placeholder for future shortcut-specific setup."""
        pass

ViewGui.setup_actions = menu_setup_actions
ViewGui.setup_menubar = setup_menubar
ViewGui.update_menu_visibility = update_menu_visibility
ViewGui.on_new_game_action = on_new_game_action
ViewGui.on_undo_action = on_undo_action
ViewGui.on_redo_action = on_redo_action
ViewGui.on_pause_action = on_pause_action
ViewGui.on_hint_action = on_hint_action
ViewGui.ask_file_path = ask_file_path
ViewGui.on_save_game_action = on_save_game_action
ViewGui.on_load_game_action = on_load_game_action
ViewGui.on_config_action = on_config_action
ViewGui.on_info_action = on_info_action
ViewGui.on_customize_shortcuts_action = on_customize_shortcuts_action
ViewGui.setup_config_screen = setup_config_screen
ViewGui.on_start_game_clicked = on_start_game_clicked

# Backward-compatible alias for older imports.
View_Gui = ViewGui
