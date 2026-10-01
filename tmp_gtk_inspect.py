import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gdk
print([name for name in dir(Gdk.ModifierType) if name.endswith('_MASK')])
