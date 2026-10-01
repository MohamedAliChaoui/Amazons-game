"""Save and load game state in ASCII format (F21-F25).

Handles serialization and deserialization of the game state including
settings, board position, and move history.  Supports inline ``#``
and block ``{ }`` comments.  An optional SHA-256 checksum section
prevents manual tampering.
"""

from amazons.model.board.board import Board
from amazons.model.board.move import Move
import os
import hashlib


class SaveLoadManager:
    """Manages saving and loading of GameController state.

    All methods are static — no instance is needed.
    """

    # Salt mixed into the SHA-256 checksum to deter trivial tampering.
    # This is an *integrity* mechanism, not a security secret — the goal is
    # to detect accidental or naive edits of save files, not to protect
    # against a determined adversary who has access to this source code.
    _SALT = "amazons_pdp_2026_secret_key"

    @staticmethod
    def read_text_file(filepath):
        """Read a UTF-8 text file and return ``(success, content_or_error)``."""
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                return True, handle.read()
        except OSError as exc:
            return False, str(exc)

    @staticmethod
    def serialize_game_state(
        *,
        size,
        time_limit_per_move,
        board,
        history,
        ai_mode=None,
        ai_time=0.0,
        ai_evaluator=None,
    ):
        """Serialize one game state to the save/load text format.

        The returned text intentionally omits the optional checksum section so
        it can be reused for trusted in-memory synchronization traffic.
        """
        lines = [
            "[settings]",
            f"size={size}",
            f"time={time_limit_per_move / 60}",
        ]
        if ai_mode:
            lines.append(f"ai-mode={ai_mode}")
        lines.append(f"ai-time={ai_time}")
        if ai_evaluator:
            lines.append(f"ai-minimax-scoring={ai_evaluator}")
        lines.append("")

        current_color = "W" if not len(history) % 2 else "B"
        lines.extend(["[game]", current_color])

        board_array = board.get_board_array()
        for row in board_array:
            encoded_row = []
            for cell in row:
                if cell == "W":
                    encoded_row.append("Q")
                elif cell == "B":
                    encoded_row.append("q")
                elif cell == ".":
                    encoded_row.append("_")
                else:
                    encoded_row.append(cell)
            lines.append(" ".join(encoded_row))

        lines.append("")
        lines.append("[history]")
        lines.extend(SaveLoadManager._format_history(history, size))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def save_game(controller, filepath):
        """Save the current game to a file.

        The output file contains ``[settings]``, ``[game]``,
        ``[history]`` and ``[checksum]`` sections.

        Args:
            controller: The active ``GameController`` instance.
            filepath: Destination file path.

        Returns:
            A tuple ``(success, message)``.
        """
        try:
            content = SaveLoadManager.serialize_game_state(
                size=controller.size,
                time_limit_per_move=controller.time_limit_per_move,
                board=controller.board,
                history=controller.history,
                ai_mode=controller.ai_mode,
                ai_time=controller.ai_time,
                ai_evaluator=controller.ai_evaluator,
            )
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # Calculate and add checksum anti-cheat
            checksum = SaveLoadManager._compute_checksum(content)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n[checksum]\n")
                f.write(f"{checksum}\n")

            return True, "Game saved successfully."
        except Exception as e:
            return False, f"Failed to save game: {str(e)}"

    @staticmethod
    def _format_history(history, size):
        lines = []
        for index in range(0, len(history), 2):
            turn_number = index // 2 + 1
            moves = []
            for move, color in history[index:index + 2]:
                start = Move.to_algebraic(move.start_pos, size)
                end = Move.to_algebraic(move.end_pos, size)
                arrow = Move.to_algebraic(move.arrow_pos, size)
                moves.append(f"{color} {start}-{end}/{arrow}")
            lines.append(f"{turn_number}. " + "; ".join(moves) + ";")
        return lines

    @staticmethod
    def load_game(controller, filepath, skip_checksum=False):
        """Load a game from a file.

        Args:
            controller: The ``GameController`` to update.
            filepath: Path to the save file.
            skip_checksum: If ``True`` skip integrity verification.

        Returns:
            A tuple ``(success, message)``.
        """
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}"

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_content = f.read()
            return SaveLoadManager.load_game_from_text(
                controller, raw_content, skip_checksum=skip_checksum
            )
        except Exception as e:
            return False, f"Failed to parse and load game: {str(e)}"

    @staticmethod
    def load_game_from_text(controller, raw_content, skip_checksum=False):
        """Load a game from raw text content.

        Args:
            controller: The ``GameController`` to update.
            raw_content: Full file content as a string.
            skip_checksum: If ``True`` skip integrity verification.

        Returns:
            A tuple ``(success, message)``.
        """
        # Snapshot controller state so we can roll back on failure.
        _snap_size = controller.size
        _snap_time = controller.time_limit_per_move
        _snap_timers = dict(controller.timers)
        _snap_ai_mode = controller.ai_mode
        _snap_ai_time = controller.ai_time
        _snap_ai_evaluator = controller.ai_evaluator
        _snap_board = controller.board.copy()
        _snap_history = list(controller.history)
        _snap_redo = list(controller.redo_history)

        def _rollback():
            controller.size = _snap_size
            controller.time_limit_per_move = _snap_time
            controller.timers = _snap_timers
            controller.ai_mode = _snap_ai_mode
            controller.ai_time = _snap_ai_time
            controller.ai_evaluator = _snap_ai_evaluator
            controller.board = _snap_board
            controller.history = _snap_history
            controller.redo_history = _snap_redo

        try:

            # Old saves may not have a checksum section yet.
            # Only verify when one is present and checksum checks
            # are enabled.
            if not skip_checksum and "[checksum]" in raw_content:
                is_valid, msg = SaveLoadManager._verify_checksum(
                    raw_content
                )
                if not is_valid:
                    return False, msg

            # Remove [checksum] section before parsing
            content = SaveLoadManager._strip_checksum_section(raw_content)

            # Remove block comments { ... }
            content = SaveLoadManager._remove_block_comments(content)

            lines = content.split("\n")

            # Remove inline comments # ...
            lines = [line.split("#")[0].strip() for line in lines]
            lines = [line for line in lines if line]  # Remove empty lines

            settings = {}
            board_lines = []
            history_lines = []
            current_section = None
            current_turn_color = None

            for line in lines:
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1].lower()
                    continue

                if current_section == "settings":
                    if "=" in line:
                        key, val = line.split("=", 1)
                        settings[key.strip()] = val.strip()
                elif current_section == "game":
                    if current_turn_color is None and line in (
                        "W",
                        "B",
                        "w",
                        "b",
                    ):
                        current_turn_color = line.upper()
                    else:
                        # Validate it's a board line
                        # Lines can look like "_ _ Q _ X"
                        cleaned_line = line.replace(" ", "")
                        if cleaned_line and set(cleaned_line).issubset(
                            set("_QqXWB.")
                        ):
                            board_lines.append(cleaned_line)
                elif current_section == "history":
                    history_lines.append(line)

            # 1. Apply Settings
            if "size" in settings:
                loaded_size = int(settings["size"])
                if not (4 <= loaded_size <= 11):
                    return False, (
                        f"Invalid board size: {loaded_size}. "
                        "Expected a value between 4 and 11."
                    )
                controller.size = loaded_size
            if "time" in settings:
                controller.time_limit_per_move = float(settings["time"]) * 60
                controller.timers = {
                    "W": controller.time_limit_per_move,
                    "B": controller.time_limit_per_move,
                }
            if "ai-mode" in settings:
                controller.ai_mode = settings["ai-mode"]
            if "ai-time" in settings:
                controller.ai_time = float(settings["ai-time"])
            if "ai-minimax-scoring" in settings:
                controller.ai_evaluator = settings["ai-minimax-scoring"]
            # 2. Reconstruct Board
            if board_lines:
                size = controller.size
                if len(board_lines) != size:
                    # Soft warning: adapt the size to the loaded
                    # board when possible.
                    size = len(board_lines)
                    controller.size = size
                controller.board = Board(size)  # Clear standard init
                controller.board.white_bb = 0
                controller.board.black_bb = 0
                controller.board.arrow_bb = 0

                for r, row_str in enumerate(board_lines):
                    if r >= size:
                        break
                    for c, char in enumerate(row_str):
                        if c >= size:
                            break
                        pos = r * size + c
                        if char in ("Q", "W"):
                            controller.board.white_bb |= 1 << pos
                        elif char in ("q", "B"):
                            controller.board.black_bb |= 1 << pos
                        elif char == "X":
                            controller.board.arrow_bb |= 1 << pos
            else:
                # Settings-only saves should still leave the controller in a
                # consistent state for the loaded size.
                controller.board = Board(controller.size)

            # 3. Apply History
            controller.history = []
            controller.redo_history = []
            full_history_text = " ".join(history_lines)

            history_commands = [
                cmd.strip()
                for cmd in full_history_text.split(";")
                if cmd.strip()
            ]
            for cmd in history_commands:
                parts = cmd.split()
                if len(parts) >= 2:
                    # Example format: "1. W e2-e4/e6" or "B g8-f6/f3"
                    if parts[0].endswith("."):
                        if len(parts) >= 3:
                            color = parts[1]
                            move_str = parts[2]
                        else:
                            continue
                    else:
                        color = parts[0]
                        move_str = parts[1]

                    if "/" in move_str and "-" in move_str:
                        move_part, arrow_part = move_str.split("/")
                        if "-" in move_part:
                            start_alg, end_alg = move_part.split("-")
                            try:
                                move = Move(
                                    Move.from_algebraic(
                                        start_alg, controller.size
                                    ),
                                    Move.from_algebraic(
                                        end_alg, controller.size
                                    ),
                                    Move.from_algebraic(
                                        arrow_part, controller.size
                                    ),
                                )
                                controller.history.append((move, color))
                            except ValueError:
                                # Ignore invalid move algebraic
                                # notation in history.
                                pass

            # Validate loaded board
            valid, validation_msg = SaveLoadManager._validate_board(controller)
            if not valid:
                _rollback()
                return False, validation_msg

            return True, "Game loaded successfully."
        except Exception as e:
            _rollback()
            return False, f"Failed to parse and load game: {str(e)}"

    @staticmethod
    def _remove_block_comments(text):
        result = []
        i = 0
        in_comment = False
        while i < len(text):
            if not in_comment and text[i] == "{":
                in_comment = True
                i += 1
            elif in_comment and text[i] == "}":
                in_comment = False
                i += 1
            else:
                if not in_comment:
                    result.append(text[i])
                i += 1
        return "".join(result)

    @staticmethod
    def _compute_checksum(content):
        """Calculate SHA-256 hash of content with secret salt."""
        salted = SaveLoadManager._SALT + content
        return hashlib.sha256(salted.encode("utf-8")).hexdigest()

    @staticmethod
    def _verify_checksum(raw_content):
        """Verify that the file checksum matches the content."""
        if "[checksum]" not in raw_content:
            return False, "Missing checksum: file rejected."

        # Separate content from checksum
        content_before = SaveLoadManager._strip_checksum_section(raw_content)
        # Extract stored checksum
        checksum_section = raw_content.split("[checksum]")[1]
        stored_hash = checksum_section.strip().split("\n")[0].strip()

        # Recalculate expected checksum
        expected_hash = SaveLoadManager._compute_checksum(content_before)

        if stored_hash != expected_hash:
            return False, (
                "Invalid checksum: the save file "
                "has been modified. Loading refused."
            )
        return True, ""

    @staticmethod
    def _strip_checksum_section(raw_content):
        """Remove [checksum] section from raw content."""
        if "[checksum]" in raw_content:
            return raw_content.split("\n[checksum]")[0]
        return raw_content

    @staticmethod
    def _validate_board(controller):
        """Logical validation of the loaded board."""
        board = controller.board
        size = controller.size

        if size == 4:
            expected_queens = 2
        elif size == 5:
            expected_queens = 3
        else:
            expected_queens = 4

        # Count white and black queens
        white_count = board.white_bb.bit_count()
        black_count = board.black_bb.bit_count()

        # Verify at least 1 queen of each color
        if not white_count:
            return False, ("Invalid board: no white queens found.")
        if not black_count:
            return False, ("Invalid board: no black queens found.")

        # Verify that the number of queens is equal
        if white_count != black_count:
            return False, (
                f"Invalid board: {white_count} white queens "
                f"vs {black_count} black queens."
            )

        # Verify the expected number of queens per side for this board size.
        if white_count != expected_queens:
            return False, (
                f"Invalid board: expected {expected_queens} queens per side, "
                f"got {white_count}."
            )

        # Verify that no piece overlaps another
        overlap = (
            (board.white_bb & board.black_bb)
            | (board.white_bb & board.arrow_bb)
            | (board.black_bb & board.arrow_bb)
        )
        if overlap:
            return False, ("Invalid board: pieces overlap.")

        # Verify that positions are within bounds
        max_bit = size * size
        all_pieces = board.white_bb | board.black_bb | board.arrow_bb
        if all_pieces >= (1 << max_bit):
            return False, ("Invalid board: positions out of bounds.")

        # Verify history consistency: number of arrows
        history_len = len(controller.history)
        arrow_count = board.arrow_bb.bit_count()
        if arrow_count != history_len:
            return False, (
                f"Invalid board: {arrow_count} arrows on the "
                f"board but {history_len} moves in history."
            )

        return True, ""
    
