"""Shared network utilities for the Amazons project."""

from queue import Empty


class NetworkQueueMixin:
    """Provides buffered message queue handling for network entities."""

    @property
    def inbox(self):
        """Expose the buffered inbox while draining queued messages."""
        self._drain_message_queue()
        return self._pending_messages

    @inbox.setter
    def inbox(self, messages):
        """Replace the pending buffered messages."""
        self._pending_messages = list(messages)

    def _notify_message_received(self, message):
        """Invoke the optional message callback safely."""
        callback = getattr(self, "on_message_received", None)
        if not callback:
            return
        try:
            callback(message)
        except TypeError:
            try:
                callback()
            except Exception:
                pass
        except Exception:
            pass

    def _drain_message_queue(self):
        """Move queued messages into the local pending buffer."""
        while True:
            try:
                self._pending_messages.append(
                    self._message_queue.get_nowait()
                )
            except Empty:
                break

    def drain_messages(self):
        """Return and clear all currently pending messages."""
        self._drain_message_queue()
        messages = list(self._pending_messages)
        self._pending_messages.clear()
        return messages
