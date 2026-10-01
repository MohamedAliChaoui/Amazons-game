"""Keyboard shortcuts management for the GTK GUI.

This module handles loading, saving, and applying customizable keyboard
shortcuts for the Amazons GUI, with persistent storage in .amazonsrc.
"""

import builtins
import configparser
import re
from pathlib import Path

from amazons.constants import DEFAULT_SHORTCUTS


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    return getattr(builtins, "_", lambda s: s)(message)


CONFIG_FILE = Path.home() / ".amazonsrc"

def load_shortcuts():
    """Load custom shortcuts from .amazonsrc config file.

    Returns:
        Dictionary mapping action names to GTK accelerator strings.
        Falls back to DEFAULT_SHORTCUTS if config file does not exist.
    """
    if not CONFIG_FILE.exists():
        return DEFAULT_SHORTCUTS.copy()

    config = configparser.ConfigParser()
    try:
        config.read(CONFIG_FILE, encoding="utf-8")
        if "shortcuts" not in config:
            config["shortcuts"] = DEFAULT_SHORTCUTS.copy()
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as file:
                    config.write(file)
            except OSError:
                pass
            return DEFAULT_SHORTCUTS.copy()

        shortcuts = DEFAULT_SHORTCUTS.copy()
        for action, default_accel in DEFAULT_SHORTCUTS.items():
            if action in config["shortcuts"]:
                shortcuts[action] = config["shortcuts"][action]
        return shortcuts
    except configparser.Error:
        return DEFAULT_SHORTCUTS.copy()


def save_shortcuts(shortcuts):
    """Save custom shortcuts to .amazonsrc config file.

    Args:
        shortcuts: Dictionary mapping action names to GTK accelerator strings.
    """
    config = configparser.ConfigParser()

    # Preserve existing config sections
    if CONFIG_FILE.exists():
        try:
            config.read(CONFIG_FILE, encoding="utf-8")
        except configparser.Error:
            pass

    # Create or update the shortcuts section
    if "shortcuts" not in config:
        config["shortcuts"] = {}

    for action, accel in shortcuts.items():
        normalized = normalize_accelerator(accel)
        config["shortcuts"][action] = normalized or accel

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            config.write(file)
    except OSError as exc:
        print(f"Warning: Failed to save shortcuts to {CONFIG_FILE}: {exc}")


def normalize_accelerator(accel):
    """Parse a PyGTK-like accelerator string and return a normalized string."""
    # pylint: disable=too-many-branches,too-many-statements,too-complex
    if accel is None:
        return ""
    accel = accel.strip()
    if not accel:
        return ""

    parts = []
    key = None
    tokens = re.findall(r"<[^>]+>|[^<>\+\s-]+", accel)

    for token in tokens:
        clean = token.strip()
        if not clean:
            continue
        if clean.startswith("<") and clean.endswith(">"):
            clean = clean[1:-1]

        low = clean.lower()
        if low in ("ctrl", "control"):
            parts.append("<Control>")
            continue
        if low in ("alt",):
            parts.append("<Alt>")
            continue
        if low in ("shift",):
            parts.append("<Shift>")
            continue
        if low in ("super", "meta", "win", "windows"):
            parts.append("<Super>")
            continue
        if low in ("hyper",):
            parts.append("<Hyper>")
            continue

        if low == "comma":
            key = "comma"
            continue
        if low == "space":
            key = "space"
            continue
        if low == "enter":
            key = "Return"
            continue
        # pylint: disable=too-many-boolean-expressions
        if low in {'escape', 'esc'}:
            key = "Escape"
            continue
        elif low in {'delete', 'del'}:
            key = "Delete"
            continue
        elif low == 'backspace':
            key = "BackSpace"
            continue
        elif low in {"left", "right", "up", "down", "home", "end", "pageup", "pagedown"}:
            key = low.capitalize()
            continue

        key = low

        if len(key) == 1 and key.isalpha():
            key = key.upper()

    if not key:
        return ""
    return "".join(parts) + key


def apply_shortcuts(app_window, shortcuts):
    """Apply keyboard shortcuts to the GTK application window.

    Args:
        app_window: The Gtk.ApplicationWindow instance.
        shortcuts: Dictionary mapping action names to GTK accelerator strings.
    """
    app = app_window.get_application()
    if not app:
        return

    for action_name, accel in shortcuts.items():
        if not accel:
            continue
        accel = normalize_accelerator(accel)
        if not accel:
            continue
        full_action_name = f"win.{action_name}"
        try:
            app.set_accels_for_action(full_action_name, [accel])
        except Exception:
            pass


def customize_shortcuts_dialog(app_window, shortcuts):
    """Open a modal GTK dialog to customize keyboard shortcuts.

    Args:
        app_window: The Gtk.ApplicationWindow instance.
        shortcuts: Dictionary mapping action names to GTK accelerator strings.

    Returns:
        Updated shortcuts dictionary if user clicks OK, None if cancelled.
    """
    # pylint: disable=too-many-branches,too-many-statements,too-complex,too-many-locals
    # pylint: disable=import-outside-toplevel
    from gi.repository import Gtk, GLib

    dialog = Gtk.Dialog(
        title=_("Customize Keyboard Shortcuts"),
        transient_for=app_window,
        modal=True,
    )
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Save"), Gtk.ResponseType.OK)
    from amazons.view.ui.utils import setup_dialog_content_box
    content_box = setup_dialog_content_box(dialog)

    # Create scrollable list of shortcuts
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_min_content_height(300)

    list_box = Gtk.ListBox()
    list_box.set_selection_mode(Gtk.SelectionMode.NONE)

    from gi.repository import Gdk

    ALT_MASK = getattr(Gdk.ModifierType, "ALT_MASK", None)
    if ALT_MASK is None:
        ALT_MASK = getattr(Gdk.ModifierType, "MOD1_MASK", 0)

    SUPER_MASK = getattr(Gdk.ModifierType, "SUPER_MASK", None)
    if SUPER_MASK is None:
        SUPER_MASK = getattr(Gdk.ModifierType, "META_MASK", 0)

    active_entry = None

    def set_active_entry(entry):
        nonlocal active_entry
        active_entry = entry
        return False

    def clear_active_entry(*_args):
        nonlocal active_entry
        active_entry = None
        return False

    def on_dialog_key_press(_controller, keyval, _keycode, state):
        # pylint: disable=too-many-branches,import-outside-toplevel
        if active_entry is None:
            return False

        modifiers = []
        if state & Gdk.ModifierType.CONTROL_MASK:
            modifiers.append("<Control>")
        if ALT_MASK and state & ALT_MASK:
            modifiers.append("<Alt>")
        if state & Gdk.ModifierType.SHIFT_MASK:
            modifiers.append("<Shift>")
        if SUPER_MASK and state & SUPER_MASK:
            modifiers.append("<Super>")

        key_name = Gdk.keyval_name(keyval)
        if not key_name:
            return False

        key_name = key_name.lower()
        if key_name in (
            "shift_l",
            "shift_r",
            "control_l",
            "control_r",
            "alt_l",
            "alt_r",
            "super_l",
            "super_r",
        ):
            return True

        accel_text = "".join(modifiers) + key_name
        normalized = normalize_accelerator(accel_text)
        if normalized:
            active_entry.set_text(normalized)
            return True
        return False

    dialog_key_controller = Gtk.EventControllerKey.new()
    dialog_key_controller.connect("key-pressed", on_dialog_key_press)
    dialog.add_controller(dialog_key_controller)

    entries = {}
    for action_name, default_accel in DEFAULT_SHORTCUTS.items():
        current_accel = shortcuts.get(action_name, default_accel)

        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_start(10)
        hbox.set_margin_end(10)
        hbox.set_margin_top(5)
        hbox.set_margin_bottom(5)

        # Action label
        label = Gtk.Label(label=_(action_name.replace("_", " ").title()))
        label.set_xalign(0)
        label.set_hexpand(True)

        # Entry for shortcut
        entry = Gtk.Entry()
        entry.set_text(current_accel)
        entry.set_width_chars(20)
        entry.set_tooltip_text(
            _("Click here and press the new shortcut combination, e.g. Ctrl+K")
        )
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect(
            "enter",
            lambda *args, entry=entry: set_active_entry(entry),
        )
        focus_controller.connect(
            "leave",
            lambda *args: clear_active_entry(),
        )
        entry.add_controller(focus_controller)
        entries[action_name] = entry

        # Reset button
        reset_btn = Gtk.Button(label=_("Reset"))
        reset_btn.connect(
            "clicked",
            lambda b, action=action_name, entry=entry: entry.set_text(
                DEFAULT_SHORTCUTS[action]
            ),
        )

        hbox.append(label)
        hbox.append(entry)
        hbox.append(reset_btn)
        row.set_child(hbox)
        list_box.append(row)

    scroll.set_child(list_box)
    content_box.append(scroll)

    result = None
    loop = GLib.MainLoop()

    def on_response(dialog, response):
        nonlocal result
        if response == Gtk.ResponseType.OK:
            result = {action: entry.get_text() for action, entry in entries.items()}
        dialog.destroy()
        loop.quit()

    dialog.connect("response", on_response)
    dialog.show()
    loop.run()

    return result
