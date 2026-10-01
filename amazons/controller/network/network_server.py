"""TCP server with UDP LAN discovery for network play.

The server accepts multiple TCP clients, tracks their lobby state,
and broadcasts its presence via UDP so that clients on the same LAN
can discover it automatically.
"""

import base64
import builtins
from queue import Queue
import socket
import threading
import time

from amazons.controller.save_load_manager import SaveLoadManager
from amazons.model.board.board import Board
from amazons.model.board.move import Move


def _(message: str) -> str:
    """Lookup a translated string via the global ``_`` installed by gettext."""
    translator = getattr(builtins, "_", None)
    if translator is None or translator is _:
        return message
    return translator(message)


from amazons.controller.network.message_queue import NetworkQueueMixin


class NetworkServer(NetworkQueueMixin):
    """TCP game server with UDP broadcast discovery.

    Attributes:
        server_name: Human-readable name advertised via UDP.
        tcp_port: Port used for the TCP game connection.
        udp_port: Port used for broadcasting presence.
        running: ``True`` while the server is active.
        client_socket: Connected client socket, or ``None``.
        inbox: Buffered received messages awaiting processing.
    """

    def __init__(self, server_name="AmazonsServer"):
        self.server_name = server_name
        self.tcp_port = 12345
        self.udp_port = 12346
        self.broadcast_interval = 10.0
        self.inactivity_timeout = 60.0
        self.listen_backlog = 5
        self.running = False
        self.tcp_thread = None
        self.udp_thread = None
        self.client_socket = None
        self.server_socket = None
        self.client_address = None
        self._client_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._message_queue = Queue()
        self._pending_messages = []
        self.on_message_received = None
        self._player_threads = {}
        self.connected_players = {}
        self._next_player_id = 1
        self.active_player_id = None
        self.host_player_id = "HOST"
        self.host_player = {"name": None, "status": "idle"}
        self.scoreboard = {}
        self.pending_invitations = {}
        self.invitation_timeout = 300.0
        self.undo_request_timeout = 30.0
        self.default_board_size = 10
        self.default_time_limit = 1800.0
        self.active_sessions = {}
        self.player_sessions = {}
        self._next_session_id = 1

    def start(self, port=12345):
        """Start the TCP listener and UDP broadcaster.

        Args:
            port: TCP port to bind to.

        Returns:
            ``None`` on success, or an error message string on failure.
        """
        if self.running:
            return "Server is already running."
        self.tcp_port = port
        try:
            self.server_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM
            )
            self.server_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            self.server_socket.bind(("", self.tcp_port))
            self.server_socket.listen(self.listen_backlog)
            self.server_socket.settimeout(1.0)
        except Exception as e:
            return f"Error starting TCP server: {e}"

        self.running = True
        self.tcp_thread = threading.Thread(
            target=self._tcp_listener, daemon=True
        )
        self.udp_thread = threading.Thread(
            target=self._udp_broadcaster, daemon=True
        )

        self.tcp_thread.start()
        self.udp_thread.start()
        return None

    def stop(self, notify_client=True):
        """Stop the server and close all sockets."""
        self.running = False
        with self._state_lock:
            player_ids = list(self.connected_players.keys())

        if notify_client:
            if player_ids:
                for player_id in player_ids:
                    self._notify_client("SERVER_STOP", player_id=player_id)
            else:
                self._notify_client("SERVER_STOP")

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None
        if player_ids:
            for player_id in player_ids:
                self._close_client(player_id=player_id)
        else:
            self._close_client()

        if self.tcp_thread:
            self.tcp_thread.join(timeout=2.0)
        if self.udp_thread:
            self.udp_thread.join(timeout=2.0)
        for thread in list(self._player_threads.values()):
            thread.join(timeout=1.0)
        self._player_threads.clear()

    def _udp_broadcaster(self):
        """Send a UDP broadcast at regular intervals for LAN discovery."""
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = f"{self.server_name}:{self.tcp_port}".encode("utf-8")

        while self.running:
            try:
                udp_sock.sendto(message, ("<broadcast>", self.udp_port))
            except Exception:
                pass
            # Sleep in small increments to respond to self.running faster.
            sleep_slices = max(1, int(self.broadcast_interval / 0.1))
            for _ in range(sleep_slices):
                if not self.running:
                    break
                time.sleep(0.1)
        udp_sock.close()

    def _tcp_listener(self):
        """Accept TCP connections and handle incoming messages."""
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                player_id = self._register_player(client, addr)
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client, player_id),
                    daemon=True,
                )
                with self._state_lock:
                    self._player_threads[player_id] = thread
                thread.start()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                print(f"[DEBUG SERVER] TCP Listener error: {e}")
                break

    def _handle_client(self, client, player_id=None):
        """Read messages from the connected client in a loop.

        Special protocol messages (``PING``, ``QUIT``) are handled
        directly; all other messages are added to the pending inbox.
        """
        client.settimeout(1.0)
        buffer = ""
        last_activity = time.monotonic()
        while self.running:
            try:
                data = client.recv(1024)
                if not data:
                    break

                last_activity = time.monotonic()
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    message = line.strip()
                    if not message:
                        continue

                    msg_upper = message.upper()
                    if msg_upper == "PING":
                        client.sendall(b"PONG\n")
                    elif msg_upper == "KEEPALIVE":
                        continue
                    elif msg_upper == "QUIT":
                        client.sendall(b"BYE\n")
                        break
                    elif msg_upper.startswith("NAME "):
                        self._update_player(
                            player_id,
                            name=message[5:].strip() or self._default_player_name(player_id),
                        )
                        self._message_queue.put(message)
                        self._notify_message_received(message)
                    elif msg_upper.startswith("INVITE "):
                        target_id = message[7:].strip().upper()
                        result = self.request_invitation(player_id, target_id)
                        self.send(result, player_id=player_id)
                    elif msg_upper == "ACCEPT":
                        result = self.respond_to_invitation(
                            player_id, accepted=True
                        )
                        self.send(result, player_id=player_id)
                    elif msg_upper == "DECLINE":
                        result = self.respond_to_invitation(
                            player_id, accepted=False
                        )
                        self.send(result, player_id=player_id)
                    elif msg_upper == "CANCEL":
                        result = self.cancel_invitation(player_id)
                        self.send(result, player_id=player_id)
                    elif self._handle_client_game_message(player_id, message):
                        continue
                    else:
                        self._message_queue.put(message)
                        self._notify_message_received(message)
            except socket.timeout:
                if time.monotonic() - last_activity >= self.inactivity_timeout:
                    if player_id is None:
                        self._notify_client("TIMEOUT")
                    else:
                        self._notify_client("TIMEOUT", player_id=player_id)
                    break
                continue
            except OSError as e:
                if not self.running or getattr(e, "winerror", None) == 10038:
                    break
                print(f"[DEBUG SERVER] Client handler error: {e}")
                break
            except Exception as e:
                print(f"[DEBUG SERVER] Client handler error: {e}")
                break

        print("[DEBUG SERVER] Client connection closed.")
        self._close_client(client, player_id=player_id)

    def send(self, msg, player_id=None):
        """Sends a message to the connected client."""
        return self._notify_client(msg, player_id=player_id)

    def receive(self):
        """Pop and return the oldest pending message.

        Returns:
            A message string, or ``None`` if no message is pending.
        """
        self._drain_message_queue()
        if self._pending_messages:
            return self._pending_messages.pop(0)
        return None

    def get_status(self):
        """Return a summary of the current server state."""
        with self._state_lock:
            players = list(self.connected_players.values())
            active_sessions = len(self.active_sessions)
            ingame_in_sessions = set()
            for session in self.active_sessions.values():
                ingame_in_sessions.update(session["player_colors"].keys())
            standalone_ingame = sum(
                1
                for p in players
                if p["status"] == "ingame" and p["id"] not in ingame_in_sessions
            )

        return {
            "running": self.running,
            "port": self.tcp_port,
            "connected_clients": len(players),
            "parties_in_progress": active_sessions
            + standalone_ingame
            + (1 if self.host_player["status"] == "ingame" else 0),
            "active_player_id": self.active_player_id,
        }

    def get_players(self):
        """Return connected players sorted by numeric player id."""
        with self._state_lock:
            players = [
                {
                    "id": player["id"],
                    "name": player["name"],
                    "status": player["status"],
                    "address": player["address"],
                }
                for player in self.connected_players.values()
            ]

        def sort_key(player):
            try:
                return int(player["id"][1:])
            except (ValueError, IndexError):
                return 0

        return sorted(players, key=sort_key)

    def get_player(self, player_id):
        """Return one player description, or ``None`` if missing."""
        with self._state_lock:
            player = self.connected_players.get(player_id)
            if not player:
                return None
            return {
                "id": player["id"],
                "name": player["name"],
                "status": player["status"],
                "address": player["address"],
            }

    def set_active_player(self, player_id):
        """Select the remote player used for the next hosted game."""
        with self._state_lock:
            if player_id is not None and player_id not in self.connected_players:
                return False
            self.active_player_id = player_id

        self._refresh_active_client()
        return True

    def set_player_status(self, player_id, status):
        """Update a player's status if they are connected."""
        self._update_player(player_id, status=status)

    def set_host_player(self, name, status="idle"):
        """Remember the local host player displayed by server commands."""
        self.host_player = {
            "name": (name or "Host").strip() or "Host",
            "status": status,
        }
        self._ensure_score_entry(self.host_player["name"])

    def begin_hosted_game(self, host_name, player_id=None):
        """Mark the current hosted network game as active."""
        self.set_host_player(host_name, status="ingame")
        if player_id is not None:
            self.set_player_status(player_id, "ingame")

    def end_hosted_game(self):
        """Return host and active remote player to idle state."""
        if self.host_player["name"]:
            self.host_player["status"] = "idle"
        if self.active_player_id is not None:
            self.set_player_status(self.active_player_id, "idle")

    def record_completed_game(self, host_result, remote_result, player_id=None):
        """Update scoreboard entries after a hosted network game ends."""
        host_name = self.host_player["name"] or "Host"
        remote_name = None
        if player_id is not None:
            remote = self.get_player(player_id)
            if remote:
                remote_name = remote["name"]
        if remote_name is None and self.active_player_id is not None:
            remote = self.get_player(self.active_player_id)
            if remote:
                remote_name = remote["name"]

        self._record_score(host_name, host_result)
        if remote_name:
            self._record_score(remote_name, remote_result)
        self.end_hosted_game()

    def get_scoreboard(self):
        """Return scoreboard entries sorted by player name."""
        return [
            {"name": name, **stats}
            for name, stats in sorted(self.scoreboard.items())
        ]

    def get_pending_invitations(self, actor_id=None):
        """Return pending invitations, optionally filtered for one actor."""
        self._prune_expired_invitations()
        invitations = list(self.pending_invitations.values())
        if actor_id is not None:
            invitations = [
                invitation
                for invitation in invitations
                if invitation["from_id"] == actor_id
                or invitation["to_id"] == actor_id
            ]
        return sorted(invitations, key=lambda invitation: invitation["created_at"])

    def request_invitation(self, inviter_id, invitee_id):
        """Create a pending invitation between two idle players."""
        self._prune_expired_invitations()
        inviter = self._get_actor(inviter_id)
        invitee = self._get_actor(invitee_id)

        if not inviter:
            return "ERROR Unknown inviter."
        if not invitee:
            return "ERROR Unknown player ID."
        if inviter["id"] == invitee["id"]:
            return "ERROR You cannot invite yourself."
        if inviter["status"] != "idle":
            return "ERROR You are not available."
        if invitee["status"] != "idle":
            return "ERROR Target player is not available."
        if self._find_pending_invitation(inviter_id=inviter["id"]):
            return "ERROR You already have a pending invitation."
        if self._find_pending_invitation(invitee_id=invitee["id"]):
            return "ERROR Target player already has a pending invitation."

        invitation = {
            "from_id": inviter["id"],
            "from_name": inviter["name"],
            "to_id": invitee["id"],
            "to_name": invitee["name"],
            "created_at": time.time(),
        }
        self.pending_invitations[invitee["id"]] = invitation
        self._set_actor_status(inviter["id"], "waitgame")
        self._set_actor_status(invitee["id"], "waitgame")
        self._notify_actor(
            invitee["id"],
            f"INVITE_FROM {inviter['id']} {inviter['name']}",
        )
        return f"INVITE_SENT {invitee['id']} {invitee['name']}"

    def respond_to_invitation(self, invitee_id, accepted):
        """Accept or decline the pending invitation for one player."""
        self._prune_expired_invitations()
        invitation = self._find_pending_invitation(invitee_id=invitee_id)
        if not invitation:
            return "ERROR No pending invitation."

        inviter_id = invitation["from_id"]
        invitee = self._get_actor(invitee_id)
        inviter = self._get_actor(inviter_id)
        if not invitee or not inviter:
            self._clear_invitation(invitation)
            return "ERROR Invitation is no longer valid."

        if accepted:
            self.pending_invitations.pop(invitation["to_id"], None)
            self._notify_actor(
                inviter_id,
                f"INVITE_ACCEPTED {invitee['id']} {invitee['name']}",
            )
            if inviter_id == self.host_player_id:
                self.set_active_player(invitee_id)
                self.begin_hosted_game(inviter["name"], player_id=invitee_id)
                self._message_queue.put(f"HOST_START_GAME {invitee_id}")
                self._notify_message_received(f"HOST_START_GAME {invitee_id}")
            else:
                match_error = self.start_client_match(
                    inviter_id,
                    invitee_id,
                    size=self.default_board_size,
                    time_limit=self.default_time_limit,
                )
                if match_error:
                    self._set_actor_status(inviter_id, "idle")
                    self._set_actor_status(invitee_id, "idle")
                    return match_error
            return f"INVITE_ACCEPTED {inviter_id} {inviter['name']}"

        self._clear_invitation(invitation)
        self._notify_actor(
            inviter_id,
            f"INVITE_DECLINED {invitee['id']} {invitee['name']}",
        )
        return f"INVITE_DECLINED {inviter_id} {inviter['name']}"

    def cancel_invitation(self, inviter_id):
        """Cancel the outgoing invitation sent by one player."""
        self._prune_expired_invitations()
        invitation = self._find_pending_invitation(inviter_id=inviter_id)
        if not invitation:
            return "ERROR No pending invitation to cancel."

        self._clear_invitation(invitation)
        self._notify_actor(
            invitation["to_id"],
            f"INVITE_CANCELLED {invitation['from_id']} {invitation['from_name']}",
        )
        return (
            f"INVITE_CANCELLED {invitation['to_id']} "
            f"{invitation['to_name']}"
        )

    def start_client_match(self, player_one_id, player_two_id, size=None, time_limit=None):
        """Start a server-relayed match between two connected clients."""
        if player_one_id == player_two_id:
            return "ERROR Select two different players."

        with self._state_lock:
            player_one = self.connected_players.get(player_one_id)
            player_two = self.connected_players.get(player_two_id)
            if not player_one or not player_two:
                return "ERROR Unknown player ID."
            if player_one["status"] != "idle" or player_two["status"] != "idle":
                return "ERROR Both players must be idle."
            if player_one_id in self.player_sessions or player_two_id in self.player_sessions:
                return "ERROR One selected player is already in a game."

            board_size = size or self.default_board_size
            game_time_limit = (
                float(time_limit)
                if time_limit is not None
                else float(self.default_time_limit)
            )
            session_id = f"S{self._next_session_id}"
            self._next_session_id += 1
            session = {
                "id": session_id,
                "size": board_size,
                "time_limit": game_time_limit,
                "board": Board(board_size),
                "history": [],
                "players": {
                    "W": player_one_id,
                    "B": player_two_id,
                },
                "player_colors": {
                    player_one_id: "W",
                    player_two_id: "B",
                },
                "names": {
                    "W": player_one["name"],
                    "B": player_two["name"],
                },
                "pending_undo_requester_id": None,
                "pending_undo_requester_color": None,
                "pending_undo_requested_at": None,
            }
            self.active_sessions[session_id] = session
            self.player_sessions[player_one_id] = session_id
            self.player_sessions[player_two_id] = session_id
            player_one["status"] = "ingame"
            player_two["status"] = "ingame"

        notifications = [
            (player_one_id, f"NAME {session['names']['B']}"),
            (player_two_id, f"NAME {session['names']['W']}"),
            (player_one_id, f"START {board_size} BLACK {game_time_limit:.3f}"),
            (player_two_id, f"START {board_size} WHITE {game_time_limit:.3f}"),
        ]
        for target_id, message in notifications:
            if not self._notify_actor(target_id, message):
                self._finish_client_session(
                    session_id,
                    winner_color=None,
                    reason=None,
                    notify_players=False,
                    record_score=False,
                )
                return "ERROR Failed to notify both clients."

        return (
            f"CLIENT_MATCH_STARTED {player_one_id} {player_two_id}"
        )

    def _get_session_id_for_player(self, player_id):
        """Return the active relayed-session id for one player."""
        with self._state_lock:
            return self.player_sessions.get(player_id)

    def _get_session_for_player(self, player_id):
        """Return the active relayed-session dictionary for one player."""
        with self._state_lock:
            session_id = self.player_sessions.get(player_id)
            if session_id is None:
                return None
            return self.active_sessions.get(session_id)

    def _message_requires_active_game(self, msg_upper):
        """Return whether a message belongs to in-game protocol traffic."""
        return (
            msg_upper.startswith("MOVE ")
            or msg_upper.startswith("CLOCK ")
            or msg_upper.startswith("UNDO_REQ")
            or msg_upper == "UNDO_OK"
            or msg_upper == "UNDO_NO"
            or msg_upper.startswith("GAMEOVER ")
            or msg_upper.startswith("LOAD_STATE ")
        )

    def _handle_client_game_message(self, player_id, message):
        """Route one in-game protocol message when a client session is active."""
        msg_upper = message.upper()
        session = self._get_session_for_player(player_id)
        if session is not None:
            self._handle_client_session_message(session["id"], player_id, message)
            return True

        if not self._message_requires_active_game(msg_upper):
            return False

        hosted_remote_active = (
            self.host_player["status"] == "ingame"
            and self.active_player_id == player_id
        )
        if hosted_remote_active:
            return False

        if msg_upper.startswith("GAMEOVER ") or msg_upper.startswith("CLOCK "):
            return True

        self.send("ERROR No active game is associated with this player.", player_id=player_id)
        return True

    def _handle_client_session_message(self, session_id, player_id, message):
        """Validate and relay one message for a client-versus-client session."""
        msg_upper = message.upper()
        if msg_upper.startswith("MOVE "):
            self._handle_client_session_move(session_id, player_id, message[5:].strip())
            return
        if msg_upper.startswith("CLOCK "):
            self._handle_client_session_clock(session_id, player_id, message)
            return
        if msg_upper.startswith("UNDO_REQ"):
            self._handle_client_session_undo_request(session_id, player_id, message)
            return
        if msg_upper == "UNDO_OK":
            self._handle_client_session_undo_reply(session_id, player_id, accepted=True)
            return
        if msg_upper == "UNDO_NO":
            self._handle_client_session_undo_reply(session_id, player_id, accepted=False)
            return
        if msg_upper.startswith("GAMEOVER "):
            self._handle_client_session_gameover(session_id, player_id, message)
            return
        if msg_upper.startswith("LOAD_STATE "):
            self.send(
                "ERROR Save synchronization is only supported in host matches.",
                player_id=player_id,
            )

    def _parse_network_move(self, notation, size):
        """Parse one network move notation into ``(color, move)``."""
        move_text = notation.strip()
        color = None
        if move_text and move_text[0] in ("W", "B"):
            color = move_text[0]
            move_text = move_text[1:]

        path_text, arrow_text = move_text.split("/", 1)
        start_text, end_text = path_text.split("-", 1)
        move = Move(
            Move.from_algebraic(start_text, size),
            Move.from_algebraic(end_text, size),
            Move.from_algebraic(arrow_text, size),
        )
        return color, move

    def _format_network_move(self, move, color, size):
        """Serialize a validated move into canonical network notation."""
        start_text = Move.to_algebraic(move.start_pos, size)
        end_text = Move.to_algebraic(move.end_pos, size)
        arrow_text = Move.to_algebraic(move.arrow_pos, size)
        return f"MOVE {color}{start_text}-{end_text}/{arrow_text}"

    def _get_session_opponent(self, session, player_id):
        """Return the other player id in one relayed session."""
        for participant_id in session["player_colors"]:
            if participant_id != player_id:
                return participant_id
        return None

    def _handle_client_session_move(self, session_id, player_id, notation):
        """Validate and relay one move inside a relayed client session."""
        with self._state_lock:
            session = self.active_sessions.get(session_id)
            if session is None:
                return

            player_color = session["player_colors"].get(player_id)
            expected_color = "W" if not len(session["history"]) % 2 else "B"
            if player_color != expected_color:
                error_message = "ERROR It is not your turn."
                opponent_id = None
                relay_message = None
                winner_color = None
                gameover_message = None
            else:
                try:
                    notation_color, move = self._parse_network_move(
                        notation,
                        session["size"],
                    )
                except Exception:
                    error_message = "ERROR Invalid move notation."
                    opponent_id = None
                    relay_message = None
                    winner_color = None
                    gameover_message = None
                else:
                    if notation_color not in (None, player_color):
                        error_message = "ERROR Move color does not match this player."
                        opponent_id = None
                        relay_message = None
                        winner_color = None
                        gameover_message = None
                    else:
                        validation = session["board"].is_valid_move(move, player_color)
                        if validation is not True:
                            error_message = f"ERROR {validation}"
                            opponent_id = None
                            relay_message = None
                            winner_color = None
                            gameover_message = None
                        else:
                            session["board"].make_move(move, player_color)
                            session["history"].append((move, player_color))
                            self._clear_pending_undo_request(session)
                            opponent_id = self._get_session_opponent(session, player_id)
                            relay_message = self._format_network_move(
                                move,
                                player_color,
                                session["size"],
                            )
                            next_color = "B" if player_color == "W" else "W"
                            if session["board"].has_moves(next_color):
                                winner_color = None
                                gameover_message = None
                            else:
                                winner_color = player_color
                                winner_name = session["names"][winner_color]
                                gameover_message = (
                                    f"GAMEOVER WINNER={winner_color} "
                                    f"{winner_name} wins."
                                )
                            error_message = None

        if error_message:
            self.send(error_message, player_id=player_id)
            return

        if opponent_id and relay_message:
            self._notify_actor(opponent_id, relay_message)

        if winner_color and gameover_message:
            self._finish_client_session(
                session_id,
                winner_color=winner_color,
                reason=gameover_message,
            )
            return

    def _handle_client_session_clock(self, session_id, player_id, message):
        """Relay a clock snapshot to the opponent in a relayed session."""
        session = self._get_session_for_player(player_id)
        if session is None or session["id"] != session_id:
            return

        parts = message.split(maxsplit=2)
        if len(parts) != 3:
            return

        if parts[1].strip().upper() != session["player_colors"].get(player_id):
            self.send("ERROR Clock color does not match this player.", player_id=player_id)
            return

        opponent_id = self._get_session_opponent(session, player_id)
        if opponent_id:
            self._notify_actor(opponent_id, message)

    def _session_can_undo(self, session, requester_color):
        """Return whether a session still contains a move for one color."""
        return any(color == requester_color for _move, color in session["history"])

    def _session_apply_undo_batch(self, session, requester_color):
        """Undo moves in reverse order until the requester's move is removed."""
        undone = []
        while session["history"]:
            move, color = session["history"].pop()
            session["board"].undo_move(move, color)
            undone.append((move, color))
            if color == requester_color:
                break
        return undone

    def _clear_pending_undo_request(self, session):
        """Clear the pending undo metadata for one relayed session."""
        session["pending_undo_requester_id"] = None
        session["pending_undo_requester_color"] = None
        session["pending_undo_requested_at"] = None

    def _expire_stale_pending_undo_request(self, session):
        """Drop a stuck undo request after the configured timeout."""
        requested_at = session.get("pending_undo_requested_at")
        if requested_at is None:
            return
        if (time.time() - requested_at) >= self.undo_request_timeout:
            self._clear_pending_undo_request(session)

    def _serialize_session_state(self, session):
        """Encode one relayed session into the save/load text format."""
        return SaveLoadManager.serialize_game_state(
            size=session["size"],
            time_limit_per_move=session["time_limit"],
            board=session["board"],
            history=session["history"],
            ai_time=0.0,
        )

    def _build_session_state_message(self, session):
        """Build one authoritative session snapshot message."""
        payload = base64.b64encode(
            self._serialize_session_state(session).encode("utf-8")
        ).decode("ascii")
        return f"LOAD_STATE {payload}"

    def _handle_client_session_undo_request(self, session_id, player_id, message):
        """Relay one undo request to the opponent after validating it."""
        with self._state_lock:
            session = self.active_sessions.get(session_id)
            if session is None:
                return

            self._expire_stale_pending_undo_request(session)
            requester_color = session["player_colors"].get(player_id)
            if requester_color is None:
                return
            if session["pending_undo_requester_id"] is not None:
                error_message = "ERROR An undo request is already pending."
                opponent_id = None
            elif not self._session_can_undo(session, requester_color):
                error_message = "ERROR Nothing to undo."
                opponent_id = None
            else:
                session["pending_undo_requester_id"] = player_id
                session["pending_undo_requester_color"] = requester_color
                session["pending_undo_requested_at"] = time.time()
                opponent_id = self._get_session_opponent(session, player_id)
                error_message = None

        if error_message:
            self.send(error_message, player_id=player_id)
            return

        if opponent_id:
            self._notify_actor(opponent_id, f"UNDO_REQ {requester_color}")

    def _handle_client_session_undo_reply(self, session_id, player_id, accepted):
        """Process one undo response sent by the non-requesting player."""
        with self._state_lock:
            session = self.active_sessions.get(session_id)
            if session is None:
                return

            self._expire_stale_pending_undo_request(session)
            requester_id = session.get("pending_undo_requester_id")
            requester_color = session.get("pending_undo_requester_color")
            if requester_id is None or requester_color is None:
                return
            if requester_id == player_id:
                self.send("ERROR Only the opponent can answer an undo request.", player_id=player_id)
                return

            self._clear_pending_undo_request(session)
            if accepted:
                self._session_apply_undo_batch(session, requester_color)
                state_message = self._build_session_state_message(session)
                player_ids = list(session["player_colors"].keys())
                message = "UNDO_OK"
            else:
                state_message = None
                player_ids = []
                message = "UNDO_NO"

        if accepted:
            sync_ok = True
            for target_id in player_ids:
                sync_ok = self._notify_actor(target_id, state_message) and sync_ok
            if not sync_ok:
                message = "ERROR Failed to synchronize the undone game state."

        self._notify_actor(requester_id, message)

    def _handle_client_session_gameover(self, session_id, player_id, message):
        """Finalize one relayed session after a client reports game over."""
        session = self._get_session_for_player(player_id)
        if session is None or session["id"] != session_id:
            return

        payload = message[9:].strip()
        winner_color = None
        if payload.upper().startswith("WINNER="):
            winner_token = payload.split(maxsplit=1)[0].split("=", 1)[1].upper()
            if winner_token in ("W", "B"):
                winner_color = winner_token

        if winner_color not in ("W", "B"):
            winner_color = session["player_colors"].get(player_id)
        self._finish_client_session(session_id, winner_color=winner_color, reason=message)

    def _finish_client_session(
        self,
        session_id,
        winner_color=None,
        reason=None,
        notify_players=True,
        record_score=True,
    ):
        """Tear down one relayed client session and optionally notify players."""
        with self._state_lock:
            session = self.active_sessions.pop(session_id, None)
            if session is None:
                return False

            player_ids = list(session["player_colors"].keys())
            for player_id in player_ids:
                self.player_sessions.pop(player_id, None)
                player = self.connected_players.get(player_id)
                if player:
                    player["status"] = "idle"

        if record_score and winner_color in ("W", "B"):
            loser_color = "B" if winner_color == "W" else "W"
            self._record_score(session["names"][winner_color], "win")
            self._record_score(session["names"][loser_color], "loss")

        if notify_players and reason:
            for player_id in player_ids:
                self._notify_actor(player_id, reason)
        return True

    def _notify_client(self, msg, player_id=None):
        with self._client_lock:
            if player_id is not None:
                client = self._get_client_socket(player_id)
            else:
                client = self.client_socket

        if not client:
            return False

        try:
            if not msg.endswith("\n"):
                msg += "\n"
            client.sendall(msg.encode("ascii", errors="ignore"))
            return True
        except Exception as e:
            print(f"[DEBUG SERVER] Send failed: {e}")
            return False

    def _close_client(self, client=None, player_id=None):
        with self._client_lock:
            active_client = client
            if player_id is not None and active_client is None:
                active_client = self._get_client_socket(player_id)
            if active_client is None:
                active_client = self.client_socket
            if active_client is None:
                self.client_socket = None
                self.client_address = None
                if player_id is not None:
                    self._unregister_player(player_id)
                return
            if active_client is self.client_socket:
                self.client_socket = None
                self.client_address = None

        try:
            active_client.close()
        except OSError:
            pass

        if player_id is not None:
            self._unregister_player(player_id)

    def _register_player(self, client, addr):
        with self._state_lock:
            player_id = f"P{self._next_player_id}"
            self._next_player_id += 1
            self.connected_players[player_id] = {
                "id": player_id,
                "name": self._default_player_name(player_id),
                "status": "idle",
                "address": addr,
                "socket": client,
            }
            if self.active_player_id is None:
                self.active_player_id = player_id

        self._refresh_active_client()
        player_name = self._default_player_name(player_id)
        message = f"PLAYER_CONNECTED {player_id} {player_name}"
        self._message_queue.put(message)
        self._notify_message_received(message)
        return player_id

    def _unregister_player(self, player_id):
        player = self.get_player(player_id)
        player_name = (
            player["name"] if player else self._default_player_name(player_id)
        )
        session = self._get_session_for_player(player_id)
        hosted_game_interrupted = (
            self.active_player_id == player_id
            and self.host_player["status"] == "ingame"
        )
        client_session_interrupted = session is not None
        with self._state_lock:
            self.connected_players.pop(player_id, None)
            self._player_threads.pop(player_id, None)
            if self.active_player_id == player_id:
                remaining_ids = sorted(self.connected_players.keys())
                self.active_player_id = remaining_ids[0] if remaining_ids else None

        self._refresh_active_client()
        if hosted_game_interrupted:
            host_name = self.host_player["name"] or "Host"
            self._record_score(host_name, "win")
            self._record_score(player_name, "loss")
            self.host_player["status"] = "idle"
        if client_session_interrupted and self.running:
            winner_id = self._get_session_opponent(session, player_id)
            winner_color = None
            gameover_message = _("Opponent disconnected.")
            if winner_id is not None:
                winner_color = session["player_colors"].get(winner_id)
                winner_name = session["names"].get(winner_color, "Opponent")
                gameover_message = (
                    f"GAMEOVER WINNER={winner_color} {winner_name} wins. "
                    f"{player_name} disconnected."
                )
            self._finish_client_session(
                session["id"],
                winner_color=winner_color,
                reason=gameover_message,
            )
        self._clear_invitations_for_actor(player_id, player_name)

    def _update_player(self, player_id, **updates):
        with self._state_lock:
            player = self.connected_players.get(player_id)
            if not player:
                return False
            player.update(updates)
            return True

    def _get_client_socket(self, player_id):
        with self._state_lock:
            player = self.connected_players.get(player_id)
            if not player:
                return None
            return player.get("socket")

    def _refresh_active_client(self):
        with self._state_lock:
            if self.active_player_id is None:
                active = None
            else:
                active = self.connected_players.get(self.active_player_id)

        with self._client_lock:
            if active:
                self.client_socket = active.get("socket")
                self.client_address = active.get("address")
            else:
                self.client_socket = None
                self.client_address = None

    def _default_player_name(self, player_id):
        return f"Player{player_id[1:]}"

    def _get_actor(self, actor_id):
        if actor_id == self.host_player_id:
            return {
                "id": self.host_player_id,
                "name": self.host_player["name"] or "Host",
                "status": self.host_player["status"],
                "address": ("local", self.tcp_port),
            }
        return self.get_player(actor_id)

    def _set_actor_status(self, actor_id, status):
        if actor_id == self.host_player_id:
            self.host_player["status"] = status
            return True
        return self._update_player(actor_id, status=status)

    def _notify_actor(self, actor_id, message):
        if actor_id == self.host_player_id:
            self._message_queue.put(message)
            self._notify_message_received(message)
            return True
        return self.send(message, player_id=actor_id)

    def _find_pending_invitation(self, inviter_id=None, invitee_id=None):
        for invitation in self.pending_invitations.values():
            if inviter_id is not None and invitation["from_id"] != inviter_id:
                continue
            if invitee_id is not None and invitation["to_id"] != invitee_id:
                continue
            return invitation
        return None

    def _clear_invitation(self, invitation):
        self.pending_invitations.pop(invitation["to_id"], None)
        self._set_actor_status(invitation["from_id"], "idle")
        self._set_actor_status(invitation["to_id"], "idle")

    def _clear_invitations_for_actor(self, actor_id, actor_name):
        """Cancel pending invitations involving one disconnected actor."""
        impacted = [
            invitation
            for invitation in list(self.pending_invitations.values())
            if invitation["from_id"] == actor_id or invitation["to_id"] == actor_id
        ]
        for invitation in impacted:
            self._clear_invitation(invitation)
            if invitation["from_id"] == actor_id:
                target_id = invitation["to_id"]
            else:
                target_id = invitation["from_id"]
            self._notify_actor(
                target_id,
                f"INVITE_CANCELLED {actor_id} {actor_name}",
            )

    def _prune_expired_invitations(self):
        now = time.time()
        expired = [
            invitation
            for invitation in self.pending_invitations.values()
            if now - invitation["created_at"] >= self.invitation_timeout
        ]
        for invitation in expired:
            self._clear_invitation(invitation)
            self._notify_actor(
                invitation["from_id"],
                f"INVITE_EXPIRED {invitation['to_id']} {invitation['to_name']}",
            )
            self._notify_actor(
                invitation["to_id"],
                f"INVITE_EXPIRED {invitation['from_id']} {invitation['from_name']}",
            )

    def _ensure_score_entry(self, name):
        if not name:
            return None
        if name not in self.scoreboard:
            self.scoreboard[name] = {
                "wins": 0,
                "losses": 0,
                "played": 0,
            }
        return self.scoreboard[name]

    def _record_score(self, name, result):
        entry = self._ensure_score_entry(name)
        if entry is None:
            return
        entry["played"] += 1
        if result == "win":
            entry["wins"] += 1
        elif result == "loss":
            entry["losses"] += 1
