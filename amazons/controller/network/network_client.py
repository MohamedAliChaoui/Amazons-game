"""TCP client and UDP LAN discovery for network play.

:class:`NetworkClient` connects to a remote :class:`NetworkServer`
and exchanges game messages over TCP.

:class:`NetworkDiscovery` listens for UDP broadcast announcements
so the user can see available servers on the local network.
"""

from queue import Queue
import socket
import threading
import time

from amazons.controller.network.message_queue import NetworkQueueMixin


class NetworkClient(NetworkQueueMixin):
    """TCP client that connects to a game server.

    Attributes:
        connected: ``True`` while connected to a server.
        host: IP address of the remote server.
        port: TCP port of the remote server.
        inbox: Buffered received messages awaiting processing.
    """

    def __init__(self):
        self.socket = None
        self.connected = False
        self.host = None
        self.port = None
        self._message_queue = Queue()
        self._pending_messages = []
        self.receiver_thread = None
        self.keepalive_thread = None
        self.running = False
        self.disconnect_reason = None
        self.on_message_received = None
        self.keepalive_interval = 10.0

    def join(self, host="localhost", port=12345):
        """Connect to a game server.

        Args:
            host: IP address or hostname of the server.
            port: TCP port of the server.

        Returns:
            ``None`` on success, or an error message string.
        """
        if self.connected:
            return "Already connected to a server."
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((host, port))
            self.connected = True
            self.host = host
            self.port = port
            self.running = True
            self.disconnect_reason = None
            self.receiver_thread = threading.Thread(
                target=self._receive_loop, daemon=True
            )
            self.receiver_thread.start()
            self.keepalive_thread = threading.Thread(
                target=self._keepalive_loop, daemon=True
            )
            self.keepalive_thread.start()
            return None
        except Exception as e:
            return f"Connection failed: {e}"

    def ping(self):
        """Send a PING and wait for PONG to measure latency.

        Returns:
            A string with the round-trip time, or an error message.
        """
        if not self.connected:
            return "Not connected."
        try:
            start_time = time.time()
            self.send("PING")

            # Wait for PONG in inbox
            response = self._wait_for_response("PONG", timeout=5.0)
            end_time = time.time()

            if response:
                elapsed_ms = int((end_time - start_time) * 1000)
                return f"PONG TIME={elapsed_ms}ms"
            return "Ping timeout (no PONG received)"
        except Exception as e:
            return f"Ping failed: {e}"

    def quit(self):
        """Disconnect from the server gracefully.

        Returns:
            A status message string.
        """
        if not self.connected:
            return self.disconnect_reason or "Not connected."

        try:
            self.send("QUIT")
            # Wait for BYE
            response = self._wait_for_response("BYE", timeout=2.0)

            self.disconnect()
            return (
                "Disconnected. "
                f"(Server said: {response if response else 'nothing'})"
            )
        except Exception as e:
            self.connected = False
            return f"Quit error: {e}"

    def _wait_for_response(self, expected_prefix, timeout=5.0):
        """Block until a message matching *expected_prefix* arrives.

        Args:
            expected_prefix: The uppercase prefix to look for.
            timeout: Maximum wait time in seconds.

        Returns:
            The matching message, or ``None`` on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            self._drain_message_queue()
            if self._pending_messages:
                # Check if any message matches
                for i, msg in enumerate(self._pending_messages):
                    if msg.upper().startswith(expected_prefix):
                        return self._pending_messages.pop(i)
            time.sleep(0.05)
        return None

    def _receive_loop(self):
        """Background thread that reads messages from the server."""
        self.socket.settimeout(1.0)
        buffer = ""
        while self.running:
            try:
                data = self.socket.recv(1024)
                if not data:
                    self.disconnect_reason = (
                        self.disconnect_reason
                        or "Server closed the connection."
                    )
                    self.disconnect()
                    break

                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    message = line.strip()
                    if message:
                        if message.upper() in ("SERVER_STOP", "TIMEOUT"):
                            if message.upper() == "SERVER_STOP":
                                self.disconnect_reason = (
                                    "Server stopped and closed the session."
                                )
                            else:
                                self.disconnect_reason = (
                                    "Disconnected after 60 seconds of inactivity."
                                )
                            self._message_queue.put(message)
                            self.disconnect()
                            return
                        self._message_queue.put(message)
                        self._notify_message_received(message)
            except socket.timeout:
                continue
            except Exception:
                self.disconnect_reason = (
                    self.disconnect_reason or "Connection lost unexpectedly."
                )
                self.disconnect()
                break

    def _keepalive_loop(self):
        """Send periodic heartbeats so normal play does not look idle."""
        while self.running:
            if self.connected:
                self.send("KEEPALIVE")
            time.sleep(self.keepalive_interval)

    def send(self, msg):
        """Send a message to the server.

        Args:
            msg: Message string, with a newline added if missing.

        Returns:
            ``True`` on success, ``False`` on failure.
        """
        if self.connected:
            try:
                if not msg.endswith("\n"):
                    msg += "\n"
                self.socket.sendall(msg.encode("ascii", errors="ignore"))
                return True
            except Exception:
                return False
        return False

    def receive(self):
        """Pop and return the oldest pending message.

        Returns:
            A message string, or ``None`` if no message is pending.
        """
        self._drain_message_queue()
        if self._pending_messages:
            return self._pending_messages.pop(0)
        return None

    def disconnect(self):
        self.running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
        self.socket = None


class NetworkDiscovery:
    """Listen for UDP broadcast announcements from game servers.

    Attributes:
        udp_port: Port to listen on for broadcast packets.
        servers: Mapping of ``ip:port`` to server info.
        running: ``True`` while the discovery loop is active.
    """

    def __init__(self):
        self.udp_port = 12346
        self.server_timeout = 30.0
        self.servers = (
            {}
        )  # { "ip:port": {"name": "...", "last_seen": timestamp} }
        self.running = False
        self.thread = None

    def start(self):
        """Start the background discovery listener."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(
            target=self._discovery_loop, daemon=True
        )
        self.thread.start()

    def stop(self):
        """Stop the discovery listener."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _discovery_loop(self):
        """Receive UDP broadcasts and update the server list."""
        try:
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError:
            self.running = False
            return
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind to ALL interfaces to see broadcasts
        try:
            udp_sock.bind(("", self.udp_port))
        except Exception:
            return  # Likely port already in use

        udp_sock.settimeout(1.0)

        while self.running:
            try:
                data, addr = udp_sock.recvfrom(1024)
                message = data.decode("utf-8", errors="replace")
                if ":" in message:
                    name, port = message.rsplit(":", 1)
                    server_id = f"{addr[0]}:{port}"
                    self.servers[server_id] = {
                        "name": name,
                        "ip": addr[0],
                        "port": int(port),
                        "last_seen": time.time(),
                    }
            except socket.timeout:
                pass
            except Exception:
                break

            # Pruning
            now = time.time()
            self.servers = {
                k: v
                for k, v in self.servers.items()
                if now - v["last_seen"] < self.server_timeout
            }

        udp_sock.close()

    def get_server_list(self):
        """Return a list of recently seen servers."""
        now = time.time()
        self.servers = {
            k: v
            for k, v in self.servers.items()
            if now - v["last_seen"] < self.server_timeout
        }
        return list(self.servers.values())
