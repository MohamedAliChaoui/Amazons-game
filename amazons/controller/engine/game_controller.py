"""Central game controller for the Game of Amazons.

Orchestrates CLI / GUI interaction, game logic, AI turns,
network play, save/load, undo/redo, and configuration.
"""

import builtins
import base64
import binascii
import socket
import sys
import time
import logging

logger = logging.getLogger(__name__)

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import select
except ImportError:
    select = None
# Ajout pour la compatibilité GUI (F7)
from amazons.model.board.board import Board
from amazons.model.board.move import Move
from amazons.model.color import Color
from amazons.model.players.human_player import human_player
from amazons.model.players.ai_player import AIPlayer
from amazons.model.players.player import NetworkPlayer
from amazons.view.ui.cli import ViewCli
from amazons.controller.network.network_server import NetworkServer
from amazons.controller.network.network_client import (
    NetworkClient,
    NetworkDiscovery,
)
from amazons.controller.engine import command_controller
from amazons.controller.engine import display_controller
from amazons.controller.engine import move_helper_controller
from amazons.controller.engine import network_command_controller
from amazons.controller.engine import network_notification_controller
from amazons.controller.engine import player_setup_controller
from amazons.controller.engine import timer_controller
from amazons.controller.save_load_manager import SaveLoadManager

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import select
except ImportError:
    select = None

def _(message: str) -> str:
    translator = getattr(builtins, "_", None)
    if translator is None or translator is _:
        return message
    return translator(message)


class GameController:
    """Main controller that ties together the model, view, and AI.

    Handles the game loop for both CLI and GUI modes, player
    creation, network sessions, and user commands.
    """
    def __init__(
        self,
        size=10,
        time_limit_min=30.0,
        ai_mode="minimax",
        ai_time=5.0,
        ai_depth=None,
        ai_evaluator="hybrid",
        use_gui=False,
    ):
        """Initialize the game controller.

        Args:
            size: Board side length.
            time_limit_min: Per-player time budget in minutes.
            ai_mode: AI search algorithm name.
            ai_time: AI thinking time in seconds.
            ai_depth: Minimax search depth.
            ai_evaluator: Evaluation function name.
            use_gui: Launch the GTK GUI instead of the CLI.
        """
        self.cli = ViewCli()
        self.size = size
        self.use_gui = use_gui  # Mémorise le mode choisi
        self.board = Board(size)
        self.history = []
        self.players = []
        self.redo_history = []

        self.ai_mode = ai_mode
        self.ai_time = float(ai_time)
        self.ai_depth = ai_depth if ai_depth is not None else 3
        self.ai_evaluator = ai_evaluator

        self.time_limit_per_move = float(time_limit_min) * 60
        self.timers = {
            "W": self.time_limit_per_move,
            "B": self.time_limit_per_move,
        }
        self._view_gui_class = None
        
        # Networking
        self.server = NetworkServer()
        self.client = NetworkClient()
        self.discovery = NetworkDiscovery()
        try:
            self.discovery.start()
        except OSError:
            logger.warning("Network discovery could not start (no network).")
        self.is_saved = True
        self.is_start_party = False
        self.is_paused = False
        self.pending_network_host_start = False
        self.network_host_starting = False

    def format_move_notation(self, move, color):
        """Format a move as ``'W e2-e4/e6'`` notation."""
        start = Move.to_algebraic(move.start_pos, self.size)
        end = Move.to_algebraic(move.end_pos, self.size)
        arrow = Move.to_algebraic(move.arrow_pos, self.size)
        return f"{color} {start}-{end}/{arrow}"

    def _normalize_clock_color(self, color):
        """Normalize a color token to ``'W'`` or ``'B'``."""
        return timer_controller.normalize_clock_color(color)

    def _apply_remote_clock_update(self, color, remaining):
        """Apply a remote clock value to the local timers."""
        return timer_controller.apply_remote_clock_update(
            self, color, remaining
        )

    def _apply_remote_clock_message(self, message):
        """Parse and apply a ``CLOCK`` protocol message."""
        return timer_controller.apply_remote_clock_message(self, message)

    def _send_clock_update(self, color):
        """Send the current remaining time for one color to the peer."""
        return timer_controller.send_clock_update(self, color)

    def get_history_lines(self):
        """Build a list of history lines in the save-file format."""
        return display_controller.get_history_lines(self)

    def get_configuration_lines(self):
        """Return a list of strings describing current settings."""
        return display_controller.get_configuration_lines(self, _)

    def get_time_status_line(self):
        """Return a formatted string showing each player's remaining time."""
        return timer_controller.get_time_status_line(self, _)

    def close_network_session(self, notify_remote=True):
        self.server.end_hosted_game()
        if self.server.running:
            self.server.stop(notify_client=notify_remote)

        if notify_remote:
            if self.client.connected:
                self.client.send("QUIT")

        self.server.on_message_received = None
        self.client.on_message_received = None

        if self.client.connected:
            if notify_remote:
                self.client.quit()
            else:
                self.client.disconnect()

        self.client.disconnect_reason = None

        self.is_start_party = False
        self.pending_network_host_start = False
        self.network_host_starting = False

    def get_local_server_addresses(self):
        """Return a list of local IP addresses suitable for display."""
        addresses = []
        seen = set()

        def add_address(ip):
            if not ip or ip.startswith("127."):
                return
            if ip in seen:
                return
            seen.add(ip)
            addresses.append(ip)

        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.connect(("8.8.8.8", 80))
                add_address(probe.getsockname()[0])
            finally:
                probe.close()
        except OSError:
            pass

        try:
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                add_address(ip)
        except OSError:
            pass

        return addresses

    def show_history(self):
        """Print the move history to the CLI."""
        display_controller.show_history(self, _)

    def show_time(self):
        """Print the remaining time for each player."""
        display_controller.show_time(self, _)

    def show_configuration(self):
        """Print the current configuration settings."""
        display_controller.show_configuration(self, _)

    def show_server_status(self):
        """Print the current server status summary."""
        display_controller.show_server_status(self, _)

    def show_players(self, player_id=None):
        """Print connected players or details for one player."""
        display_controller.show_players(self, _, player_id)

    def show_scoreboard(self):
        """Print the current network scoreboard."""
        display_controller.show_scoreboard(self, _)

    def _is_player_id(self, token):
        """Return ``True`` if *token* looks like a server player id."""
        return network_notification_controller.is_player_id(token)

    def _handle_network_notification(self, message):
        """Display invitation and server-side network notifications."""
        return network_notification_controller.handle_network_notification(
            self, _, message
        )

    def resolve_opponent_type(self, parts):
        """Determine the opponent type from a ``new`` command."""
        return command_controller.resolve_opponent_type(self, _, parts)

    def handle_show_command(self, parts):
        """Dispatch a ``show`` sub-command."""
        return command_controller.handle_show_command(self, _, parts)

    def handle_network_command(self, cmd, parts):
        """Dispatch top-level network and lobby commands."""
        return network_command_controller.handle_network_command(
            self, _, cmd, parts
        )

    def handle_hint_command(self, color_code):
        """Compute and display a hint move using the AI."""
        move_helper_controller.handle_hint_command(self, _, color_code)

    def handle_set_command(self, parts):
        """Handle the ``set`` command for AI configuration values."""
        # Accept both "set PARAM=VALUE" (spec F15) and "set PARAM VALUE".
        if len(parts) == 2 and "=" in parts[1]:
            raw_param, _sep, raw_value = parts[1].partition("=")
            param = raw_param.strip().lower()
            value = raw_value.strip().lower()
        elif len(parts) == 3:
            param = parts[1].lower()
            value = parts[2].lower()
        else:
            self.cli.msg(_(
                "Usage: set <param>=<value>  or: set <param> <value>"
            ))
            self.cli.msg(_(
                "Params: ai-mode, ai-time, ai-depth, ai-evaluator"
            ))
            return

        if param == "ai-mode" or param == "ai_mode":
            if value in ("minimax", "mcts", "random", "iterative"):
                self.ai_mode = value
                self.cli.msg(_(f"ai-mode set to {value}"))
            else:
                self.cli.error(_("Invalid AI mode. Use minimax, mcts, random, or iterative."))
        elif param == "ai-time" or param == "ai_time":
            try:
                self.ai_time = float(value)
                self.cli.msg(_(f"ai-time set to {self.ai_time}"))
            except ValueError:
                self.cli.msg(_("ai-time must be a number."))
        elif param == "ai-depth" or param == "ai_depth":
            try:
                self.ai_depth = int(value)
                self.cli.msg(_(f"ai-depth set to {self.ai_depth}"))
            except ValueError:
                self.cli.msg(_("ai-depth must be an integer."))
        elif param == "ai-evaluator" or param == "ai_evaluator":
            if value in ("hybrid", "territory", "mobility"):
                self.ai_evaluator = value
                self.cli.msg(_(f"ai-evaluator set to {value}"))
            else:
                self.cli.error(_("Invalid evaluator. Use hybrid, territory, or mobility."))
        else:
            self.cli.msg(_(f"Unknown parameter '{param}'."))

    def start(self):
        """Entry point: start the CLI loop or the GTK GUI."""
        if self.use_gui:
            try:
                import gi  # type: ignore
                gi.require_version("Gtk", "4.0")  # type: ignore
                from gi.repository import Gio, Gtk  # type: ignore
                from amazons.view.ui.gui import ViewGui
            except ImportError as exc:
                self.cli.msg(
                    _(
                        "GUI unavailable: install GTK/PyGObject "
                        "or run without -g."
                    )
                )
                self.cli.msg(str(exc))
                return

            self._view_gui_class = ViewGui
            app = Gtk.Application(
                application_id="fr.ubordeaux.amazons",
                flags=Gio.ApplicationFlags.NON_UNIQUE,
            )
            app.connect("activate", self.run_gui)
            app.run(None)
            return
        else:
            self.cli.welcome(self.size)

        if getattr(self, "is_loaded_from_save", False):
            self.cli.msg(
                _("Save loaded. Please define the players to resume the game:")
            )
            adversaire = self.resolve_opponent_type(["new"])
            if adversaire:
                self.resumeGame(adversaire)

        while True:
            if (
                self.pending_network_host_start
                and self.server.running
                and self.server.client_socket
            ):
                self.pending_network_host_start = False
                self.cli.msg(
                    _("Remote player connected. Starting network game...")
                )
                self.startGame("network")
                continue

            # Poll for input with short timeout if connected
            # We use a custom non-blocking input helper
            raw = self._get_input_or_network(prompt=">> ")
            if not raw:
                continue

            if raw == "NETWORK_EVENT":
                self._handle_pending_network_event()
                continue

            parts = raw.split()

            if not parts:
                continue

            cmd = parts[0]

            if cmd in ("help", "h"):
                self.cli.show_help()
                continue

            elif cmd in ("quit", "q"):
                quit_status = self.handle_quit(in_game=self.is_start_party)
                if quit_status == "exit":
                    self.cli.msg(_("Bye!"))
                    self.discovery.stop()
                    self.server.stop(notify_client=False)
                    self.is_start_party = False
                    break
                if quit_status == "disconnect":
                    continue
            elif cmd in ("new", "n"):
                if (
                    len(parts) == 2
                    and self.server.running
                    and self._is_player_id(parts[1])
                ):
                    if not self.server.host_player["name"]:
                        host_name = self.cli.input_cli(
                            _("Your host name: ")
                        ).strip()
                        self.server.set_host_player(host_name, status="idle")
                    result = self.server.request_invitation(
                        self.server.host_player_id,
                        parts[1].upper(),
                    )
                    self._handle_network_notification(result)
                    continue
                if self.client.connected:
                    self.cli.msg(
                        _(
                            "Already connected to a server. "
                            "Waiting for Host to start..."
                        )
                    )
                    continue
                adversaire = self.resolve_opponent_type(parts)
                if adversaire is None:
                    continue
                if adversaire == "hu":
                    self.cli.msg(_("Starting new game against human..."))
                elif adversaire == "ai":
                    self.cli.msg(_("Starting new game against AI..."))
                elif adversaire == "network":
                    self.cli.msg(_("Starting network game as HOST..."))
                    self.pending_network_host_start = True
                else:
                    self.cli.msg(_("Starting new AI vs AI game..."))
                self.startGame(adversaire)
                continue

            elif cmd in ("sb"):
                if cmd == "sb" or (len(parts) > 1 and parts[1] == "board"):
                    self.handle_show_command(cmd)
                continue

            elif cmd in ("history", "hist"):
                self.cli.show_history(self.history, self.size)
                continue

            elif cmd == "set":
                self.handle_set_command(parts)
                continue

            if False:  # Removed redundant check (moved to top of loop)
                pass

            # --- NETWORK COMMANDS ---
            elif self.handle_network_command(cmd, parts):
                continue

            elif self.handle_show_command(parts):
                continue
            else:
                self.cli.msg(
                    _("Unknown command. Type help to see available commands.")
                )

    # Méthode ajoutée pour initialiser la fenêtre GUI
    def run_gui(self, app):
        """GTK application activate callback: create the GUI window."""
        window = self._view_gui_class(app, self.size, self)
        window.present()

    def _wait_for_remote_client(self, timeout=120.0, poll_interval=0.1):
        """Block until a remote client connects or timeout expires."""
        if not self.server.running:
            self.cli.msg(
                _(
                    "Start the server first with '(server start [port])' "
                    "or join the server with '(join addrs:port)'."
                )
            )
            return False

        if self.server.client_socket:
            return True

        self.cli.msg(_("Waiting for remote player to connect..."))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.server.client_socket:
                self.cli.msg(_("Remote player connected."))
                return True
            time.sleep(poll_interval)

        self.cli.msg(
            _(
                "No remote player connected yet. You can keep waiting or retry 'new network' later."
            )
        )
        return False


    def create_players(self, adversaire):
        """Create the two player objects according to the selected mode."""
        return player_setup_controller.create_players(self, _, adversaire)

    def show_possible_moves(self, action, joueur):
        """Show legal moves from a chosen square."""
        move_helper_controller.show_possible_moves(self, _, action, joueur)

    def play_turn(self):
        """Main game loop: alternate turns until game over or quit."""
        joueur_actuel = len(self.history) % 2

        while True:
            joueur = self.players[joueur_actuel]
            color_code = joueur.color_code
            color_key = joueur.couleur

            # --- VÉRIFICATION DU BLOCAGE (Jalon F10) ---
            if not self.board.has_moves(color_code):
                self.handle_end_game(f"{joueur.nom} is blocked!")
                break

            color_name = _("white") if color_code == "W" else _("black")
            self.cli.msg(
                _("\nIt's the turn of {name} ({color})").format(
                    name=joueur.nom, color=color_name
                )
            )
            self.cli.show_board(self.board.get_board_array())
            self.cli.msg(self.get_time_status_line())

            start_time = time.time()

            # ----- LOGIQUE DU TOUR -----
            if isinstance(joueur, AIPlayer):
                # --- TOUR IA ---
                self.cli.msg(_("AI is thinking..."))
                think_budget = min(self.ai_time, self.timers[color_key])
                logger.debug(f"Début de la réflexion IA pour {joueur.nom} (Budget: {think_budget:.1f}s)")
                move = joueur.get_action(self.board, think_budget)

                # Mise à jour du temps IA
                elapsed_ai = time.time() - start_time
                logger.debug(f"Action de l'IA calculée en {elapsed_ai:.3f}s")
                self.timers[color_key] -= elapsed_ai

                if self.timers[color_key] <= 0:
                    self.timers[color_key] = 0
                    self.handle_end_game(
                        f"TEMPS ÉCOULÉ pour {joueur.nom}!",
                        loser_color=color_key,
                    )
                    return

                if move:
                    # Traduction en notation algébrique (F25)
                    s_alg = Move.to_algebraic(move.start_pos, self.size)
                    e_alg = Move.to_algebraic(move.end_pos, self.size)
                    a_alg = Move.to_algebraic(move.arrow_pos, self.size)

                    self.board.make_move(move, color_code)
                    self.history.append((move, color_code))
                    self.redo_history.clear()
                    self.is_saved = False
                    self.cli.msg(
                        _(">> AI played: {move}").format(
                            move=f"{color_code}{s_alg}-{e_alg}/{a_alg}"
                        )
                    )

                    # --- SYNC MOVE ---
                    if self.server.client_socket:
                        self.server.send(
                            f"MOVE {color_code}{s_alg}-{e_alg}/{a_alg}"
                        )
                    elif self.client.connected:
                        self.client.send(
                            f"MOVE {color_code}{s_alg}-{e_alg}/{a_alg}"
                        )

                    time.sleep(1)  # Délai visuel

            elif isinstance(joueur, NetworkPlayer):
                # --- REMOTE TURN ---
                notation = joueur.get_action(self.board)
                if notation == "QUIT_GAME":
                    self.cli.msg(_("Remote player quit the game."))
                    if self._should_prompt_save_before_quit():
                        self.prompt_save_before_quit()
                    self.close_network_session(notify_remote=False)
                    return

                elif notation == "QUIT":
                    self.close_network_session(notify_remote=False)
                    self.cli.msg(_("Remote session closed."))
                    return

                elif notation.startswith("LOAD_STATE "):
                    payload = notation[len("LOAD_STATE "):].strip()
                    if self._apply_remote_loaded_game(payload):
                        joueur_actuel = len(self.history) % 2
                        continue
                    return

                elif notation == "GAMEOVER":
                    self.cli.msg(_("Remote terminal signaled Game Over."))
                    return
                elif notation == "LOCAL_UNDO":
                    # Local player wants to undo their own previous
                    # move while waiting.
                    adversaire = self.players[
                        1 - joueur_actuel
                    ]  # The RemotePlayer
                    if self.undo_turn(
                        self.players[joueur_actuel], adversaire
                    ):
                        joueur_actuel = 1 - (len(self.history) % 2)
                        continue  # Restart turn loop
                elif notation.startswith("UNDO_REQ"):
                    # Opponent wants to undo
                    parts = notation.split()
                    requester_color = parts[1] if len(parts) > 1 else None
                    resp = (
                        self.cli.input_cli(
                            _("Opponent wants to undo. Agree? (y/n): ")
                        )
                        .strip()
                        .lower()
                    )
                    if resp in ("y", "yes"):
                        if self.server.client_socket:
                            self.server.send("UNDO_OK")
                        else:
                            self.client.send("UNDO_OK")
                        self.cli.msg(
                            _(
                                "Undo accepted. Waiting for synchronized game state..."
                            )
                        )
                        continue
                    else:
                        if self.server.client_socket:
                            self.server.send("UNDO_NO")
                        else:
                            self.client.send("UNDO_NO")
                else:
                    # notation is e2-e4/e6
                    try:
                        move_part, arrow_part = notation.split("/")
                        start_alg, end_alg = move_part.split("-")
                        move = Move(
                            Move.from_algebraic(start_alg, self.size),
                            Move.from_algebraic(end_alg, self.size),
                            Move.from_algebraic(arrow_part, self.size),
                        )
                        self.board.make_move(move, color_code)
                        self.history.append((move, color_code))
                        self.redo_history.clear()
                        self.cli.msg(
                            _(">> Remote played: {move}").format(
                                move=f"{color_code}{notation}"
                            )
                        )
                        time.sleep(0.5)
                    except Exception:
                        self.cli.error(_("Error parsing remote move."))
                        return
            else:
                # --- TOUR HUMAIN ---
                while True:
                    def is_time_up():
                        if getattr(self, "is_paused", False):
                            return False
                        return (self.timers[color_key] - (time.time() - start_time)) <= 0

                    action = self._get_input_or_network(
                        prompt=(
                            _(
                                "Your action (choice, move, undo, "
                                "redo, history, show, hint, pause, save, load, help, quit): "
                            )
                        ),
                        timeout_check=is_time_up
                    ).strip()

                    if action == "time_out":
                        self.timers[color_key] = 0
                        self.handle_end_game(
                            f"TEMPS ÉCOULÉ pour {joueur.nom}!",
                            loser_color=color_key,
                        )
                        return

                    if not action:
                        continue
                    action_parts = action.split()
                    action_cmd = action_parts[0].lower()
                    # Mise à jour immédiate du temps
                    now = time.time()
                    if not self.is_paused:
                        self.timers[color_key] -= now - start_time
                    start_time = now

                    if self.timers[color_key] <= 0:
                        self.timers[color_key] = 0
                        self.handle_end_game(
                            f"TEMPS ÉCOULÉ pour {joueur.nom}!",
                            loser_color=color_key,
                        )
                        return

                    if not action:
                        continue

                    action_parts = action.split()
                    action_cmd = action_parts[0].lower()
                    if action_cmd == "network_event":
                        event_status = self._handle_pending_network_event()
                        if event_status == "loaded":
                            joueur_actuel = len(self.history) % 2
                            start_time = time.time()
                            continue
                        if event_status in ("started", "error"):
                            return
                        continue
                    if action_cmd == "QUIT":
                        return

                    if action_cmd == "quit_game":
                        self.cli.msg(_("Remote player quit the game."))
                        if self._should_prompt_save_before_quit():
                            self.prompt_save_before_quit()
                        self.close_network_session(notify_remote=False)
                        return

                    if action_cmd == "pause":
                        self.is_paused = not self.is_paused
                        if self.is_paused:
                            self.cli.msg(
                                _("Game paused. Type 'pause' to resume.")
                            )
                        else:
                            self.cli.msg(_("Game resumed."))
                            start_time = time.time()
                        continue

                    if self.is_paused and action_cmd not in (
                        "help",
                        "h",
                        "show",
                    ):
                        self.cli.msg(
                            _("Game is paused. Type 'pause' to resume.")
                        )
                        continue

                    if action_cmd in ("help", "h"):
                        self.cli.show_help()
                    elif self.handle_show_command(action_parts):
                        continue
                    elif action_cmd == "hint":
                        self.handle_hint_command(color_code)
                        continue
                    elif action_cmd == "set":
                        self.handle_set_command(action_parts)
                        continue
                    elif action_cmd == "players":
                        self.show_players(
                            action_parts[1] if len(action_parts) > 1 else None
                        )
                        continue
                    elif action_cmd == "scoreboard":
                        self.show_scoreboard()
                        continue
                    elif action_cmd == "ping":
                        self.cli.msg(_(self.client.ping()))
                        continue
                    elif (
                        action_cmd == "server"
                        and len(action_parts) > 1
                        and action_parts[1] == "status"
                    ):
                        self.show_server_status()
                        continue
                    elif action_cmd == "move":
                        if self.handle_two_step_move(joueur, action):
                            # --- SYNC MOVE ---
                            m, c = self.history[-1]
                            s_alg = Move.to_algebraic(m.start_pos, self.size)
                            e_alg = Move.to_algebraic(m.end_pos, self.size)
                            a_alg = Move.to_algebraic(m.arrow_pos, self.size)
                            if self.server.client_socket or self.client.connected:
                                self._send_clock_update(c)
                            if self.server.client_socket:
                                self.server.send(
                                    f"MOVE {c}{s_alg}-{e_alg}/{a_alg}"
                                )
                            elif self.client.connected:
                                self.client.send(
                                    f"MOVE {c}{s_alg}-{e_alg}/{a_alg}"
                                )
                            break

                    elif action_cmd == "undo":
                        n = self._parse_repeat_count(action_parts)
                        if n is None:
                            continue
                        adversaire = self.players[1 - joueur_actuel]
                        did_any = False
                        for _i in range(n):
                            if not self.undo_turn(joueur, adversaire):
                                break
                            did_any = True
                        if did_any:
                            # On veut que le prochain tour soit
                            # à len(history) % 2.
                            # Comme la boucle fait
                            # joueur_actuel = 1 - joueur_actuel à la fin,
                            # on anticipe.
                            joueur_actuel = 1 - (len(self.history) % 2)
                            break
                    elif action_cmd == "redo":
                        n = self._parse_repeat_count(action_parts)
                        if n is None:
                            continue
                        did_any = False
                        for _i in range(n):
                            if not self.redo_turn(joueur):
                                break
                            did_any = True
                        if did_any:
                            joueur_actuel = 1 - (len(self.history) % 2)
                            break
                    elif action_cmd == "choice":
                        self.show_possible_moves(action, joueur)
                        self.cli.msg(self.get_time_status_line())
                    elif action_cmd == "history" or action_cmd == "hist":
                        self.cli.show_history(self.history, self.size)
                    elif action_cmd == "save":
                        if len(action_parts) > 1:
                            success, msg = SaveLoadManager.save_game(
                                self, action_parts[1]
                            )
                            self.cli.msg(_(msg))
                            if success:
                                self.is_saved = True
                        else:
                            self.cli.msg(_("Usage: save <filename>"))
                    elif action_cmd == "load":
                        if len(action_parts) <= 1:
                            self.cli.msg(_("Usage: load <filename>"))
                            continue

                        if self.client.connected and not self.server.client_socket:
                            self.cli.msg(
                                _(
                                    "Only the host can load a saved game in network mode."
                                )
                            )
                            continue

                        success, msg = SaveLoadManager.load_game(
                            self, action_parts[1]
                        )
                        self.cli.msg(_(msg))
                        if not success:
                            continue

                        self.is_saved = True
                        if self.server.client_socket and not self._sync_loaded_game_to_remote(
                            action_parts[1]
                        ):
                            return

                        # We want the next iteration to be the
                        # correct player once the loop flips it.
                        joueur_actuel = 1 - (len(self.history) % 2)
                        break
                    elif action_cmd in ("quit", "q"):
                        if self.handle_quit(in_game=True):
                            return
                    else:
                        self.cli.msg(
                            _(
                                "Action invalide ! Tapez move, choice, "
                                "undo, show, help, redo, history, save, "
                                "load, players, scoreboard, ping, "
                                "server status ou quit."
                            )
                        )

            # Fin du tour : changement de joueur
            joueur_actuel = 1 - joueur_actuel

    def _get_input_or_network(self, prompt=">> ", timeout_check=None):
        """Read a command while also polling pending network events and custom timeouts."""
        has_pending_client_messages = bool(self.client.inbox)
        has_pending_server_messages = (
            bool(self.server.inbox) if self.server.running else False
        )
        # If we are not in a network game and don't need timeout check, use normal input.
        if not (
            self.server.running
            or self.client.connected
            or has_pending_client_messages
            or has_pending_server_messages
        ) and timeout_check is None:
            return input(prompt).strip().lower()
        print(prompt, end="", flush=True)
        buffer = ""
        while True:
            # 0. Check Custom Timeout
            if timeout_check and timeout_check():
                print("\n")
                return "time_out"

            # 1. Check Network (Non-destructive check)
            msg = None
            inbox = None
            if self.server.running:
                inbox = self.server.inbox
            elif self.client.connected or self.client.inbox:
                inbox = self.client.inbox

            if inbox:
                msg = inbox[0]  # Peek
                msg_caps = msg.upper()
                # print(f"[DEBUG POLL] Peeking at: {msg_caps}")
                # Too verbose if uncommented.

                if msg_caps.startswith("START "):
                    # Return NETWORK_EVENT but leave it in inbox for
                    # start() to handle.
                    return "NETWORK_EVENT"
                elif msg_caps.startswith("LOAD_STATE "):
                    return "NETWORK_EVENT"
                elif msg_caps.startswith("UNDO_REQ"):
                    raw_msg = inbox.pop(0)  # Consume it
                    parts = raw_msg.split()
                    requester_color = parts[1] if len(parts) > 1 else None
                    print(_("\n[REMOTE] Opponent wants to undo."))
                    resp = input(_("Agree? (y/n): ")).strip().lower()
                    if resp in ("y", "yes"):
                        if self.server.running:
                            self.server.send("UNDO_OK")
                        else:
                            self.client.send("UNDO_OK")
                        print(
                            _(
                                "Waiting for synchronized game state..."
                            )
                        )
                        return "NETWORK_EVENT"
                    else:
                        if self.server.running:
                            self.server.send("UNDO_NO")
                        else:
                            self.client.send("UNDO_NO")
                        print(prompt, end="", flush=True)
                elif msg_caps == "QUIT_GAME":
                    inbox.pop(0)
                    print(_("\n[REMOTE] Opponent quit the game."))
                    return "QUIT_GAME"
                elif msg_caps == "QUIT":
                    inbox.pop(0)
                    print(_("\n[REMOTE] Session closed."))
                    return "QUIT"

                elif msg_caps.startswith("MOVE "):
                    # Leave it in inbox for play_turn or NetworkPlayer
                    return "NETWORK_EVENT"
                elif msg_caps.startswith("GAMEOVER "):
                    inbox.pop(0)  # Consume it
                    reason = msg[9:].strip()
                    print(
                        _("\n[REMOTE] Game Over: {reason}").format(
                            reason=reason
                        )
                    )
                    return "NETWORK_EVENT"
                elif msg_caps.startswith("NAME "):
                    inbox.pop(0)
                    remote_name = msg[5:].strip()
                    for joueur in getattr(self, "players", []):
                        if isinstance(joueur, NetworkPlayer):
                            joueur.nom = remote_name
                            break
                    print(
                        _("\n[REMOTE] Player identified as: {name}").format(
                            name=remote_name
                        )
                    )
                    print(prompt, end="", flush=True)
                    continue
                else:
                    # Unrecognized message: let higher-level code
                    # handle the event.
                    return "NETWORK_EVENT"

            # 2. Check Keyboard
            if msvcrt:
                if msvcrt.kbhit():
                    try:
                        char = msvcrt.getch()
                        char = char.decode("ascii")
                        if char in ("\r", "\n"):
                            print()
                            return buffer.strip().lower()
                        elif char in ("\b", "\x08"):
                            if len(buffer) > 0:
                                buffer = buffer[:-1]
                                print("\b \b", end="", flush=True)
                        elif char.isprintable():
                            buffer += char
                            print(char, end="", flush=True)
                    except Exception:
                        pass
            elif select:
                read_ready, write_ready, error_ready = select.select(
                    [sys.stdin], [], [], 0.1
                )
                if read_ready:
                    return sys.stdin.readline().strip().lower()

            time.sleep(0.05)

    def startGame(self, adversaire, extra_param=None):
        """Initialize and start a new game."""
        self.is_start_party = True
        self.network_host_starting = adversaire == "network"
        taille = self.size

        if adversaire == "network" and not self._wait_for_remote_client():
            self.network_host_starting = False
            self.pending_network_host_start = False
            return

        if adversaire == "network":
            self.pending_network_host_start = False

        self.board = Board(taille)
        self.history = []
        self.redo_history = []

        if adversaire == "network_client":
            host_color = extra_param
            if isinstance(extra_param, dict):
                host_color = extra_param.get("host_color", "W")
                time_limit = extra_param.get("time_limit")
                if time_limit is not None:
                    self.time_limit_per_move = float(time_limit)

            color_client = "B" if Color.normalize(host_color) == "W" else "W"
            localized_color = (
                _("white") if color_client == "W" else _("black")
            )
            nom_client = self.cli.input_cli(
                _("Your name ({color}): ").format(color=localized_color)
            ).strip()
            if color_client == "W":
                self.players = [
                    human_player(nom_client, "", "W"),
                    NetworkPlayer(
                        "Remote",
                        "B",
                        self.client,
                        on_clock_received=self._apply_remote_clock_update,
                    ),
                ]
            else:
                self.players = [
                    NetworkPlayer(
                        "Remote",
                        "W",
                        self.client,
                        on_clock_received=self._apply_remote_clock_update,
                    ),
                    human_player(nom_client, "", "B"),
                ]
            # Send name to host
            self.client.send(f"NAME {nom_client}")

            # Wait for Host's NAME to update NetworkPlayer
            self.cli.msg(_("Waiting for host name..."))
            start_wait = time.time()
            host_name_found = False
            while time.time() - start_wait < 5 and not host_name_found:
                if self.client.inbox:
                    for i, msg in enumerate(self.client.inbox):
                        if msg.upper().startswith("NAME "):
                            host_name = self.client.inbox.pop(i)[5:].strip()
                            self.players[0].nom = host_name
                            self.cli.msg(
                                _("Host identified as: {host_name}").format(
                                    host_name=host_name
                                )
                            )
                            host_name_found = True
                            break
                time.sleep(0.1)
        else:
            if not self.create_players(adversaire):
                self.network_host_starting = False
                return

        self.timers = {
            "W": self.time_limit_per_move,
            "B": self.time_limit_per_move,
        }
        opponent_label = {
            "hu": _("human"),
            "ai": _("AI"),
            "aiai": _("AI vs AI"),
            "network": _("network"),
            "network_client": _("network"),
        }.get(adversaire, adversaire)
        self.cli.msg(
            _("New game {size}x{size} vs {opponent}").format(
                size=taille, opponent=opponent_label
            )
        )
        logger.info(f"Démarrage d'une nouvelle partie en {taille}x{taille} contre {adversaire}")

        self.cli.show_board(self.board.get_board_array())
        self.is_saved = True
        self.play_turn()
        self.network_host_starting = False

    def resumeGame(self, adversaire):
        """Resume a previously loaded game with the given mode."""
        if not self.create_players(adversaire):
            return
        self.cli.msg(_("Resuming loaded game..."))
        self.cli.show_board(self.board.get_board_array())
        self.is_saved = True
        self.play_turn()

    def handle_two_step_move(self, joueur, action):
        """Process a human move in two steps: queen move, then arrow shot."""
        parts = action.split()
        # Format attendu : "move e2-e4" au lieu de
        # "move r1,c1 r2,c2".
        if len(parts) < 2 or "-" not in parts[1]:
            self.cli.error(_("Format invalide. Utilisez: move e2-e4"))
            return False

        # Extraire les coordonnées de départ et d'arrivée
        # via la notation algébrique.
        try:
            coords = parts[1].split("-")
            start_pos = Move.from_algebraic(coords[0], self.size)
            end_pos = Move.from_algebraic(coords[1], self.size)
        except (ValueError, IndexError):
            self.cli.error(_("Invalid coordinates (e.g., a1, e2)."))
            return False

        color = joueur.color_code
        color_key = joueur.couleur

        # Step 1: Validate and move Queen
        try:
            validation = self.board.is_valid_queen_move(
                start_pos, end_pos, color
            )
        except Exception:
            self.cli.error(_("Invalid coordinates (e.g., a1, e2)."))
            return False
        if validation is not True:
            self.cli.error(_(f"Queen move invalid: {validation}"))
            return False

        self.board.move_queen(start_pos, end_pos, color)

        # Afficher la grille avec les tirs possibles
        targets = list(
            self.board.get_queen_moves_iterator(end_pos, self.board.occupied())
        )
        highlights = [(pos // self.size, pos % self.size) for pos in targets]
        self.cli.show_board_possible_moves(
            self.board.get_board_array(), highlights
        )

        # Step 2: Arrow shot
        while True:
            # --- MODIFICATION POUR LE BLITZ : On mesure le temps de saisie ---
            start_arrow_input = time.time()

            def is_arrow_time_up():
                if getattr(self, "is_paused", False):
                    return False
                return (self.timers[color_key] - (time.time() - start_arrow_input)) <= 0

            # Saisie de la flèche (asynchrone pour le Blitz)
            arrow_input = self._get_input_or_network(
                prompt=_("Arrow (ex: e6) | 'undo': "),
                timeout_check=is_arrow_time_up
            ).strip()

            if arrow_input == "time_out":
                self.timers[color_key] = 0
                self.handle_end_game(
                    f"TEMPS ÉCOULÉ pour {joueur.nom} pendant le tir !",
                    loser_color=color_key,
                )
                return False

            # Mise à jour du chrono pour le temps passé à choisir la flèche
            elapsed = time.time() - start_arrow_input
            self.timers[color_key] -= elapsed

            # Vérification du temps (Jalon F5)
            if self.timers[color_key] <= 0:
                self.timers[color_key] = 0
                self.handle_end_game(
                    f"TEMPS ÉCOULÉ pour {joueur.nom} pendant le tir !",
                    loser_color=color_key,
                )
                return False
            # -----------------------------------------------------------------

            # Si le joueur change d'avis et fait undo
            # avant d'avoir tiré la flèche.
            if arrow_input == "undo":
                self.board.move_queen(end_pos, start_pos, color)
                self.cli.msg(_("Move undone. Back to start."))
                self.cli.show_board(self.board.get_board_array())
                return False

            try:
                # Traduction de la position de la flèche
                arrow_pos = Move.from_algebraic(arrow_input, self.size)

                # Tirer la flèche si valide
                valid_arrow = self.board.is_valid_arrow_shot(
                    end_pos, arrow_pos
                )
                if valid_arrow is True:
                    self.board.place_arrow(arrow_pos)
                    move = Move(start_pos, end_pos, arrow_pos)
                    self.history.append((move, color))
                    # Si on joue un coup, on ne peut plus refaire
                    # les coups annulés.
                    self.redo_history.clear()
                    self.is_saved = False
                    # --- NOUVEAU FORMAT DE NOTATION (F25) ---
                    # Exemple: We2-e4/e6
                    # (Couleur + Départ - Arrivée / Flèche)
                    notation_f25 = (
                        f"{color}{coords[0]}-{coords[1]}/{arrow_input}"
                    )
                    self.cli.msg(_(f"Coup joué : {notation_f25}"))
                    # ----------------------------------------

                    return True
                else:
                    self.cli.error(_(f"Tir invalide: {valid_arrow}"))
            except Exception:
                self.cli.error(_("Position de flèche incorrecte (ex: e6)."))
                continue

    def _parse_repeat_count(self, action_parts):
        """Parse an optional positive-integer N from ``undo``/``redo`` args.

        Returns 1 if no argument is given. Returns ``None`` and prints an
        explicit error if the argument is present but not a positive int.
        """
        if len(action_parts) <= 1:
            return 1
        raw = action_parts[1]
        try:
            n = int(raw)
        except ValueError:
            self.cli.msg(_(f"Invalid count: {raw!r}. Expected a positive integer."))
            return None
        if n <= 0:
            self.cli.msg(_(f"Invalid count: {n}. Must be a positive integer."))
            return None
        return n

    def can_undo_for_player(self, joueur_demandeur):
        """Return whether *joueur_demandeur* is allowed to request an undo."""
        if not self.history:
            return False, _("Nothing to undo")

        color_demandeur = joueur_demandeur.color_code
        if not any(c == color_demandeur for _move, c in self.history):
            return False, _("You haven't made any move to undo yet.")

        return True, None

    def apply_undo_batch(self, requester_color=None, announce=True):
        """Undo the suffix of history up to the requester's last move."""
        undone_moves = []
        while self.history:
            move, color = self.history.pop()
            self.board.undo_move(move, color)
            self.redo_history.insert(0, (move, color))
            self.is_saved = False
            undone_moves.append((move, color))
            if announce:
                self.cli.msg(_(f"Move undone for {color}."))
            if requester_color is None or color == requester_color:
                break

        return undone_moves

    def undo_turn(self, joueur_demandeur, adversaire):
        """Undo the last move, with approval if required."""
        can_undo, message = self.can_undo_for_player(joueur_demandeur)
        if not can_undo:
            self.cli.msg(message)
            return False

        color_demandeur = joueur_demandeur.color_code
        logger.info("Undo request triggered by %s.", joueur_demandeur.nom)

        if isinstance(adversaire, human_player):
            while True:
                resp = (
                    self.cli.input_cli(
                        f"{adversaire.nom}, do you agree for the undo? "
                        "(yes/no): "
                    )
                    .strip()
                    .lower()
                )
                if resp in ("yes", "y"):
                    break
                if resp in ("no", "n"):
                    self.cli.msg(_(f"Undo refused by {adversaire.nom}."))
                    return False
        elif isinstance(adversaire, NetworkPlayer):
            self.cli.msg(_("Requesting undo from remote player..."))
            authoritative_host = bool(self.server.client_socket)
            if self.server.client_socket:
                self.server.send(f"UNDO_REQ {color_demandeur}")
            elif self.client.connected:
                self.client.send(f"UNDO_REQ {color_demandeur}")

            start_wait = time.time()
            granted = False
            while time.time() - start_wait < 30:
                msg = None
                if self.server.client_socket:
                    msg = self.server.receive()
                elif self.client.connected:
                    msg = self.client.receive()

                if msg:
                    msg_upper = msg.upper()
                    if msg_upper == "UNDO_OK":
                        granted = True
                        if authoritative_host:
                            break
                        continue
                    if msg_upper == "UNDO_NO":
                        self.cli.msg(_("Undo refused by remote player."))
                        return False
                    if msg_upper.startswith("LOAD_STATE "):
                        payload = msg[len("LOAD_STATE "):].strip()
                        if self._apply_remote_loaded_game(payload):
                            return True
                        self.cli.msg(
                            _(
                                "Undo accepted, but the synchronized game state could not be applied."
                            )
                        )
                        return False
                time.sleep(0.1)

            if not granted:
                self.cli.msg(_("Undo request timed out."))
                return False

            if authoritative_host:
                self.apply_undo_batch(color_demandeur, announce=True)
                if self.sync_current_state_to_remote():
                    return True
                self.cli.msg(
                    _(
                        "Undo applied locally, but failed to synchronize to the remote player."
                    )
                )
                return False

            self.cli.msg(
                _("Undo accepted. Waiting for synchronized game state...")
            )
            start_sync_wait = time.time()
            while time.time() - start_sync_wait < 30:
                msg = self.client.receive() if self.client.connected else None
                if msg and msg.upper().startswith("LOAD_STATE "):
                    payload = msg[len("LOAD_STATE "):].strip()
                    if self._apply_remote_loaded_game(payload):
                        return True
                    self.cli.msg(
                        _(
                            "Undo accepted, but the synchronized game state could not be applied."
                        )
                    )
                    return False
                time.sleep(0.1)

            self.cli.msg(
                _("Undo accepted, but the synchronized game state did not arrive.")
            )
            return False

        self.apply_undo_batch(color_demandeur, announce=True)
        return True

    def undo_remote_requested(self, requester_color=None):
        """Perform an undo triggered by the remote player."""
        if not self.history:
            return
        self.apply_undo_batch(requester_color, announce=True)

    def redo_turn(self, joueur_demandeur):
        """Redo the last undone move."""
        if any(
            isinstance(joueur, NetworkPlayer)
            for joueur in getattr(self, "players", [])
        ):
            self.cli.msg(_("Redo is not supported in network games."))
            return False

        if not self.redo_history:
            self.cli.msg(_("Nothing to redo"))
            return False

        color_demandeur = joueur_demandeur.color_code

        if self.redo_history[0][1] != color_demandeur:
            self.cli.msg(_("Nothing to redo for you yet; wait for your opponent to redo first."))
            return False

        while self.redo_history:
            move, color = self.redo_history.pop(0)
            self.board.make_move(move, color)
            self.history.append((move, color))
            self.cli.msg(_(f"Coup refait pour {color}."))
            self.is_saved = False

            if color == color_demandeur:
                break

        # Symmetric redo: mirror the undo "one full round" semantics.
        # Restore the opponent's next move (human or AI) so that
        # `undo` and `redo` are inverses. Then keep restoring any
        # trailing AI moves (degenerate case where multiple AI replies
        # were stacked) until we reach another human or run out.
        if self.redo_history:
            _m, next_color = self.redo_history[0]
            if next_color != color_demandeur:
                m, c = self.redo_history.pop(0)
                self.board.make_move(m, c)
                self.history.append((m, c))
                idx_joueur = 0 if c == "W" else 1
                if isinstance(self.players[idx_joueur], AIPlayer):
                    self.cli.msg(_(f"Coup IA restauré pour {c}."))
                else:
                    self.cli.msg(_(f"Coup adverse restauré pour {c}."))
                self.is_saved = False

        while self.redo_history:
            _m, next_color = self.redo_history[0]
            idx_joueur = 0 if next_color == "W" else 1
            if isinstance(self.players[idx_joueur], AIPlayer):
                m, c = self.redo_history.pop(0)
                self.board.make_move(m, c)
                self.history.append((m, c))
                self.cli.msg(_(f"Coup IA restauré pour {c}."))
                self.is_saved = False
            else:
                break

        return True

    def handle_end_game(self, reason, loser_color=None):
        """Handle the end of a game: display scores and winner."""
        if self.server.client_socket:
            self.server.send(f"GAMEOVER {reason}")
        elif self.client.connected:
            self.client.send(f"GAMEOVER {reason}")

        self.cli.msg(_("\n*** GAME OVER ***"))
        self.cli.msg(_(f"Raison : {reason}"))

        # Calcul des scores de territoire via le Board
        score_w, score_b = self.board.calculate_territory_scores()
        self.cli.msg(
            _(
                "Scores de territoire finaux -> "
                f"White: {score_w} | Black: {score_b}"
            )
        )

        # Déterminer le vainqueur selon la couleur qui a perdu.
        host_result = None
        remote_result = None
        if loser_color and Color.normalize(loser_color) == "W":
            host_result, remote_result = "loss", "win"
            self.cli.msg(_("RÉSULTAT : BLACK WINS (White a perdu au temps)!"))
        elif loser_color and Color.normalize(loser_color) == "B":
            host_result, remote_result = "win", "loss"
            self.cli.msg(_("RÉSULTAT : WHITE WINS (Black a perdu au temps)!"))
        elif "blocked" in reason.lower():
            # Si un joueur est bloqué, l'autre gagne
            if (
                "white" in reason.lower()
                or self.players[0].nom.lower() in reason.lower()
            ):
                self.cli.msg(_("RÉSULTAT : BLACK WINS!"))
            else:
                self.cli.msg(_("RÉSULTAT : WHITE WINS!"))
        else:
            # En cas d'autre fin, on compare les scores
            if score_w > score_b:
                self.cli.msg(_("RÉSULTAT : WHITE WINS!"))
            elif score_b > score_w:
                self.cli.msg(_("RÉSULTAT : BLACK WINS!"))
            else:
                self.cli.msg("RÉSULTAT : ÉGALITÉ !")

        if self.server.active_player_id and host_result and remote_result:
            self.server.record_completed_game(
                host_result,
                remote_result,
                player_id=self.server.active_player_id,
            )

    def prompt_save_before_quit(self):
        """Ask the user whether to save before quitting."""
        if hasattr(self, "is_saved") and not self.is_saved and self.history:
            while True:
                resp = (
                    self.cli.input_cli(
                        _("Save the game before quitting? [y/N] ")
                    )
                    .strip()
                    .lower()
                )
                if resp in ("y", "yes"):
                    filepath = self.cli.input_cli(
                        _("Enter file path: ")
                    ).strip()
                    success, msg = SaveLoadManager.save_game(self, filepath)
                    self.cli.msg(_(msg))
                    if not success:
                        continue  # Ask again if error F16
                    self.is_saved = True
                    return True
                elif resp in ("n", "no", ""):
                    return True
                else:
                    self.cli.msg(_("Please answer y or n."))
        return True

    def _should_prompt_save_before_quit(self):
        """Return True when this side should offer a save prompt."""
        if self.is_saved or not self.history:
            return False

        network_context = (
            bool(getattr(self.server, "running", False))
            or bool(getattr(self.client, "connected", False))
            or any(
                isinstance(joueur, NetworkPlayer)
                for joueur in getattr(self, "players", [])
            )
        )
        if network_context:
            return bool(getattr(self.server, "running", False))

        return True

    def handle_quit(self, in_game=False):
        has_network = (
            bool(getattr(self.server, "running", False))
            and getattr(self.server, "client_socket", None) is not None
        ) or bool(getattr(self.client, "connected", False))

        if self._should_prompt_save_before_quit():
            if not self.prompt_save_before_quit():
                return None

        if has_network:
            if in_game:
                if self.server.client_socket:
                    self.server.send("QUIT_GAME")
                elif self.client.connected:
                    self.client.send("QUIT_GAME")
            self.close_network_session(notify_remote=False)
            self.cli.msg(_("Network session closed."))
            return "disconnect"

        return "exit"

    def _sync_loaded_game_to_remote(self, filepath):
        """Send a loaded save file to the remote player for sync."""
        if not self.server.client_socket:
            return True

        success, raw_content = SaveLoadManager.read_text_file(filepath)
        if not success:
            self.cli.msg(
                _("Failed to read save file for sync: {error}").format(
                    error=raw_content
                )
            )
            return False

        payload = base64.b64encode(raw_content.encode("utf-8")).decode(
            "ascii"
        )
        if not self.server.send(f"LOAD_STATE {payload}"):
            self.cli.msg(_("Failed to synchronize loaded game to client."))
            return False

        self.cli.msg(_("Loaded game synchronized to remote player."))
        return True

    def _encode_current_state_for_sync(self):
        """Serialize the current controller state for trusted sync traffic."""
        raw_content = SaveLoadManager.serialize_game_state(
            size=self.size,
            time_limit_per_move=self.time_limit_per_move,
            board=self.board,
            history=self.history,
            ai_mode=self.ai_mode,
            ai_time=self.ai_time,
            ai_evaluator=self.ai_evaluator,
        )
        return base64.b64encode(raw_content.encode("utf-8")).decode("ascii")

    def sync_current_state_to_remote(self):
        """Push the current authoritative state to the connected client."""
        if not self.server.client_socket:
            return True
        payload = self._encode_current_state_for_sync()
        return self.server.send(f"LOAD_STATE {payload}")

    def _apply_remote_loaded_game(self, encoded_payload):
        """Apply a base64-encoded save received from the remote host."""
        try:
            raw_content = base64.b64decode(
                encoded_payload,
                validate=True,
            ).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            self.cli.msg(_(f"Failed to decode remote save: {exc}"))
            return False

        success, message = SaveLoadManager.load_game_from_text(
            self, raw_content
        )
        self.cli.msg(_(message))
        if success:
            self.is_saved = True
            self.cli.msg(_("Game state updated from host."))
            self.cli.show_board(self.board.get_board_array())
        return success

    def _handle_pending_network_event(self):
        """Handle pending network messages while the CLI is idle."""
        server_inbox = self.server.inbox if self.server.running else None
        if server_inbox:
            for index, msg in enumerate(list(server_inbox)):
                if self._handle_network_notification(msg):
                    if index < len(server_inbox):
                        server_inbox.pop(index)
                    return "server_event"

        client_inbox = self.client.inbox
        if client_inbox:
            for index, msg in enumerate(list(client_inbox)):
                msg_upper = msg.upper()

                if self._handle_network_notification(msg):
                    if index < len(client_inbox):
                        client_inbox.pop(index)
                    return "client_event"

                if msg_upper.startswith("START "):
                    if index < len(client_inbox):
                        client_inbox.pop(index)
                    parts_start = msg.split()
                    size = int(parts_start[1])
                    host_color = parts_start[2].upper()
                    time_limit = None
                    if len(parts_start) >= 4:
                        try:
                            time_limit = float(parts_start[3])
                        except ValueError:
                            time_limit = None
                    host_color_label = (
                        _("white")
                        if Color.normalize(host_color) == "W"
                        else _("black")
                    )
                    self.cli.msg(
                        _(
                            "\n[NETWORK] Host started game: "
                            "Size {size}, Host is {host_color}"
                        ).format(size=size, host_color=host_color_label)
                    )
                    self.size = size
                    self.startGame(
                        "network_client",
                        {
                            "host_color": host_color,
                            "time_limit": time_limit,
                        },
                    )
                    return "started"

                if msg_upper.startswith("LOAD_STATE "):
                    if index < len(client_inbox):
                        client_inbox.pop(index)
                    payload = msg[len("LOAD_STATE "):].strip()
                    return (
                        "loaded"
                        if self._apply_remote_loaded_game(payload)
                        else "error"
                    )

            return "pending"

        return "none"
