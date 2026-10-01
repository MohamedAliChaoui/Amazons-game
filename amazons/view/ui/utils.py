"""Common GTK utility functions for the Amazons GUI."""

from gi.repository import Gtk


def setup_dialog_content_box(dialog):
    """Refactored setup for dialog content areas."""
    dialog.set_default_response(Gtk.ResponseType.OK)
    content_box = dialog.get_content_area()
    content_box.set_spacing(10)
    content_box.set_margin_start(12)
    content_box.set_margin_end(12)
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(12)
    return content_box


def show_info_message(parent, message):
    """Display a simple informational dialog."""
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=message,
    )
    dialog.connect("response", lambda d, r: d.destroy())
    dialog.show()
