"""Small reusable helpers for GTK dialogs."""


def configure_dialog_content_box(content_box, spacing=10, margin=12):
    """Apply the standard spacing and margins to a dialog content box."""
    content_box.set_spacing(spacing)
    content_box.set_margin_start(margin)
    content_box.set_margin_end(margin)
    content_box.set_margin_top(margin)
    content_box.set_margin_bottom(margin)


def show_info_dialog(parent, gtk_module, message):
    """Show a standard informational GTK dialog."""
    dialog = gtk_module.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=gtk_module.MessageType.INFO,
        buttons=gtk_module.ButtonsType.OK,
        text=message,
    )
    dialog.connect("response", lambda current, _response: current.destroy())
    dialog.show()
