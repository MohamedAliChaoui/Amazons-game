"""Color constants for the Game of Amazons.

A single convention is used throughout: ``'W'`` for white, ``'B'`` for black.
Use :meth:`Color.to_name` only when a human-readable string is needed
for display (e.g. ``"white"`` / ``"black"``).
Use :meth:`Color.normalize` only at system boundaries (network, file load)
to convert external input to the canonical code.
"""


class Color:
    """String constants and helpers for player colors."""

    W = "W" 
    B = "B"

    @staticmethod
    def to_code(value):
        """Strict validation — only accepts ``'W'`` or ``'B'``.

        Args:
            value: Color string.

        Returns:
            ``'W'`` or ``'B'``.

        Raises:
            ValueError: If *value* is not ``'W'`` or ``'B'``.
        """
        if value not in ("W", "B"):
            raise ValueError(
                f"Invalid color code: {value!r}. Expected 'W' or 'B'."
            )
        return value

    @staticmethod
    def normalize(value):
        """Lenient conversion used only at system boundaries.

        Accepts ``'W'``, ``'B'``, ``'w'``, ``'b'``, ``'white'``, ``'black'``.

        Args:
            value: Raw color string from external input.

        Returns:
            ``'W'`` or ``'B'``.

        Raises:
            ValueError: If *value* cannot be recognized as a color.
        """
        if value in ("W", "B"):
            return value
        if isinstance(value, str):
            lower = value.lower()
            if lower in ("w", "white"):
                return "W"
            if lower in ("b", "black"):
                return "B"
        raise ValueError(f"Cannot normalize color: {value!r}")

    @staticmethod
    def to_name(code):
        """Convert ``'W'``/``'B'`` to a human-readable display string.

        Args:
            code: ``'W'`` or ``'B'``.

        Returns:
            ``'white'`` or ``'black'``.

        Raises:
            ValueError: If *code* is not ``'W'`` or ``'B'``.
        """
        if code not in ("W", "B"):
            raise ValueError(
                f"Invalid color code: {code!r}. Expected 'W' or 'B'."
            )
        return "white" if code == "W" else "black"
