"""Menu and dialog helpers for the split GTK GUI.

This module keeps menu actions, keyboard shortcuts, save/load dialogs,
and informational popups separate from the live board logic in
``gui.py``.
"""

import builtins

from amazons.controller.save_load_manager import SaveLoadManager
from amazons.model.players.ai_player import AIPlayer
from amazons.view.ui.dialog_utils import (
    configure_dialog_content_box,
    show_info_dialog,
)
from amazons.view.ui.gui_shortcuts import load_shortcuts

from gi.repository import Gio, Gtk


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    translator = getattr(builtins, "_", None)
    if translator is None or translator is _:
        return message
    return translator(message)


def setup_actions(self):
    """Create window actions and bind their keyboard accelerators."""
    # Load shortcuts from config file (F29)
    shortcuts = load_shortcuts()
    self.window_actions = {}

    actions = [
        ("new_game", self.on_new_game_action, "new_game"),
        ("save_game", self.on_save_game_action, "save_game"),
        ("load_game", self.on_load_game_action, "load_game"),
        ("quit", lambda *_: self.close(), "quit"),
        ("undo", self.on_undo_action, "undo"),  # F29: Customizable
        ("redo", self.on_redo_action, "redo"),  # F29: Customizable
        ("pause", self.on_pause_action, "pause"),
        ("hint", self.on_hint_action, "hint"),
        ("info", self.on_info_action, "info"),
        ("config", self.on_config_action, "config"),
        ("customize_shortcuts", self.on_customize_shortcuts_action, None),  # F29
    ]

    for name, callback, shortcut_key in actions:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        self.window_actions[name] = action
        # Apply shortcut from config file (skip customize_shortcuts as it has no default)
        if shortcut_key:
            accel = shortcuts.get(shortcut_key, shortcuts.get(name, ""))
            if accel:
                self.app.set_accels_for_action(f"win.{name}", [accel])


def setup_menubar(self):
    """Build the application header and initialize the menu button."""
    header = Gtk.HeaderBar()
    self.menu_button = Gtk.MenuButton()
    self.menu_button.set_icon_name("open-menu-symbolic")
    header.pack_start(self.menu_button)
    self.set_titlebar(header)
    self.update_menu_visibility(show_game_menu=False)


def update_menu_visibility(self, show_game_menu):
    """Refresh the menu entries to match whether a live game is active."""
    self.menu_shows_game_actions = show_game_menu
    menu_model = Gio.Menu()

    file_menu = Gio.Menu()
    file_menu.append(_("New Game"), "win.new_game")
    file_menu.append(_("Load Game"), "win.load_game")
    file_menu.append(_("Save Game"), "win.save_game")
    file_menu.append(_("Configuration"), "win.config")
    file_menu.append(_("Customize Shortcuts"), "win.customize_shortcuts")  # F29
    file_menu.append(_("Info"), "win.info")
    file_menu.append(_("Quit"), "win.quit")
    menu_model.append_submenu(_("File"), file_menu)

    if show_game_menu:
        game_menu = Gio.Menu()
        game_menu.append(_("Undo"), "win.undo")
        game_menu.append(_("Redo"), "win.redo")
        game_menu.append(_("Pause"), "win.pause")
        game_menu.append(_("Hint"), "win.hint")
        menu_model.append_submenu(_("Game"), game_menu)

    self.menu_button.set_menu_model(menu_model)
    self.menu_model = menu_model

    enabled_states = {
        "undo": show_game_menu,
        "redo": show_game_menu,
        "pause": show_game_menu,
        "hint": show_game_menu,
        "save_game": show_game_menu,
    }
    for action_name, is_enabled in enabled_states.items():
        action = self.window_actions.get(action_name)
        if action is not None:
            action.set_enabled(is_enabled)


def on_new_game_action(self, *_args):
    """Return to the configuration screen for a new game."""
    self.game_over = False
    self.controller.is_start_party = False
    self.setup_config_screen()
    if not self._network_session_active():
        return

    self.mode_combo.set_active_id("network")
    self.network_role_combo.set_active_id(self.network_role or "host")
    if self.network_role == "host":
        self._refresh_network_players_list()
    self._ensure_network_polling()


def on_undo_action(self, *_args):
    """Forward the menu undo action to the board handler."""
    self.on_undo_clicked(None)


def on_redo_action(self, *_args):
    """Redo the next available move and refresh the board."""
    if self.is_network_game():
        self._set_network_status(_("Redo is not supported in network games."))
        self.show_message(_("Redo is not supported in network games."))
        return

    # Silently check if there's anything to redo before calling redo_turn
    # to avoid "Nothing to redo" messages in GUI
    if not self.controller.redo_history:
        return

    idx = len(self.controller.history) % 2
    joueur = self.controller.players[idx]

    # Also check if the next redo move is for this player
    if self.controller.redo_history[0][1] != joueur.color_code:
        return

    if self.controller.redo_turn(joueur):
        self.refresh_board()
        self.refresh_status_label()


def on_pause_action(self, *_args):
    """Toggle pause state and update the status label."""
    self.paused = not self.paused
    if self.paused:
        self.lbl_status.set_markup(
            f"<span foreground='blue'>{_('PAUSED')}</span>"
        )
    else:
        self.refresh_status_label()


def on_hint_action(self, *_args):
    """Compute and display a short AI hint for the current player."""
    if self.game_over or self.paused:
        return

    # Affiche un message d'attente
    self.lbl_status.set_markup(
        f"<span foreground='#e67e22'><b>{_('Calculating hint...')}</b></span>"
    )
    
    # Force la mise à jour immédiate de l'interface (vide la file d'attente GTK)
    # pylint: disable=import-outside-toplevel
    from gi.repository import GLib
    while GLib.MainContext.default().iteration(False):
        pass

    idx = len(self.controller.history) % 2
    color = "W" if not idx else "B"
    hint_ai = AIPlayer("Hint", color, ai_mode="minimax", ai_depth=2)
    move = hint_ai.get_action(self.controller.board, time_limit=1.0)
    
    # Restaure l'affichage normal du statut
    self.refresh_status_label()

    if move:
        from amazons.model.board.move import Move
        s_coord = Move.to_algebraic(move.start_pos, self.size)
        e_coord = Move.to_algebraic(move.end_pos, self.size)
        a_coord = Move.to_algebraic(move.arrow_pos, self.size)

        msg = _(
            "The AI suggests: {color} {start}-{end}/{arrow}\n"
            "Green: start from {start}\n"
            "Yellow: move to {end}\n"
            "Orange: place the arrow on {arrow}"
        ).format(
            color=color,
            start=s_coord,
            end=e_coord,
            arrow=a_coord,
        )
        self.show_message(msg)

        path_hints = {
            (move.start_pos // self.size, move.start_pos % self.size): "hint-start-tile",
            (move.end_pos // self.size, move.end_pos % self.size): "hint-end-tile",
            (move.arrow_pos // self.size, move.arrow_pos % self.size): "hint-arrow-tile",
        }
        self.refresh_board(hints=path_hints)


def show_message(self, message):
    """Display a simple informational dialog."""
    show_info_dialog(self, Gtk, message)


def ask_file_path(self, title, button_label, callback):
    """Prompt the user for a file path and pass it to *callback*."""
    dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(button_label, Gtk.ResponseType.OK)
    content_box = dialog.get_content_area()
    configure_dialog_content_box(content_box)

    label = Gtk.Label(label=_("File name:"))
    label.set_halign(Gtk.Align.START)
    entry = Gtk.Entry()
    entry.set_activates_default(True)

    content_box.append(label)
    content_box.append(entry)

    def on_response(current_dialog, response):
        filepath = entry.get_text().strip()
        current_dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not filepath:
            self.show_message(_("Please enter a file name."))
            return
        callback(filepath)

    dialog.connect("response", on_response)
    dialog.show()


def on_save_game_action(self, *_args):
    """Open the save dialog and persist the current game state."""
    def save_to_file(filepath):
        success, msg = SaveLoadManager.save_game(self.controller, filepath)
        if success:
            self.controller.is_saved = True
            if hasattr(self, "lbl_status"):
                self.lbl_status.set_label(msg)
            else:
                self.show_message(msg)
        else:
            self.show_message(msg)

    self.ask_file_path(
        _("Save Game"),
        _("Save"),
        save_to_file,
    )


def on_load_game_action(self, *_args):
    """Open the load dialog and restore a saved game."""
    def load_from_file(filepath):
        if (
            self.is_network_game()
            and self.controller.client.connected
            and not self.controller.server.client_socket
        ):
            self.show_message(
                _("Only the host can load a saved game in network mode.")
            )
            return

        success, msg = SaveLoadManager.load_game(
            self.controller,
            filepath,
        )
        if not success:
            self.show_message(msg)
            return

        self.size = self.controller.size
        self.game_over = False
        self.paused = False
        self.selected_pos = None
        self.queen_moved_pos = None
        self.waiting_for_arrow = False
        self.controller.is_start_party = True
        self.controller.is_saved = True
        self.launch_game_board()
        self.show_message(msg)

        if self.is_network_game() and self.controller.server.client_socket:
            if not self.sync_loaded_game_to_remote(filepath):
                self.show_message(
                    _("Failed to synchronize the loaded game with the remote player.")
                )

    self.ask_file_path(
        _("Load Game"),
        _("Load"),
        load_from_file,
    )


def on_config_action(self, *_args):
    """Return to the configuration screen when a game is active."""
    if getattr(self, "menu_shows_game_actions", False):
        self.on_new_game_action()


def on_info_action(self, *_args):
    """Show the application information dialog."""
    self.show_message(_("Amazons v1.0\nAuthors: PDP Team 2026"))


def on_customize_shortcuts_action(self, *_args):
    """Open the keyboard shortcuts customization dialog (F29)."""
    # pylint: disable=import-outside-toplevel
    from amazons.view.ui.gui_shortcuts import (
        customize_shortcuts_dialog,
        save_shortcuts,
        load_shortcuts,
        apply_shortcuts,
    )

    shortcuts = load_shortcuts()
    result = customize_shortcuts_dialog(self, shortcuts)
    if result:
        save_shortcuts(result)
        apply_shortcuts(self, result)
        self.show_message(
            _("Keyboard shortcuts have been updated and saved.")
        )
