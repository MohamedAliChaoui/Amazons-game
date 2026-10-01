"""Helpers for network-related CLI commands in the game controller."""

import time


def handle_network_command(controller, translator, cmd, parts):
    """Handle top-level network and lobby commands."""
    if cmd == "server":
        if len(parts) > 1 and parts[1] == "list":
            controller.cli.msg(translator("Scanning for servers..."))
            servers = []
            deadline = time.time() + 6.0
            while time.time() < deadline:
                servers = controller.discovery.get_server_list()
                if servers:
                    break
                time.sleep(0.2)
            if not servers:
                controller.cli.msg(translator("No servers found on LAN."))
                controller.cli.msg(
                    translator(
                        "Tip: try a direct connection with "
                        "'join <host-ip>:<port>'."
                    )
                )
            else:
                controller.cli.msg(translator("\nAvailable Servers:"))
                for server in servers:
                    controller.cli.msg(
                        translator(
                            f"- {server['name']} at {server['ip']}:{server['port']}"
                        )
                    )
            return True

        if len(parts) > 1 and parts[1] == "start":
            port = int(parts[2]) if len(parts) > 2 else 12345
            err = controller.server.start(port)
            if err:
                controller.cli.msg(translator(err))
            else:
                controller.cli.msg(
                    translator("Server started on port {port}.").format(
                        port=port
                    )
                )
                local_addresses = controller.get_local_server_addresses()
                if local_addresses:
                    controller.cli.msg(
                        translator("Share one of these IPs with the other PC:")
                    )
                    for ip in local_addresses:
                        controller.cli.msg(f"  - {ip}:{port}")
                else:
                    controller.cli.msg(
                        translator(
                            "Could not detect a LAN IP "
                            "automatically. Use 'ipconfig' "
                            "to find it."
                        )
                    )
            return True

        if len(parts) > 1 and parts[1] == "stop":
            controller.server.stop()
            controller.cli.msg(translator("Server stopped."))
            return True

        if len(parts) > 1 and parts[1] == "status":
            controller.show_server_status()
            return True

        controller.cli.msg(
            translator("Usage: server list | start [port] | stop | status")
        )
        return True

    if cmd == "players":
        controller.show_players(parts[1] if len(parts) > 1 else None)
        return True

    if cmd == "scoreboard":
        controller.show_scoreboard()
        return True

    if cmd == "match":
        if not controller.server.running:
            controller.cli.msg(translator("Start the server first."))
        elif len(parts) != 3:
            controller.cli.msg(translator("Usage: match <player1_id> <player2_id>"))
        else:
            result = controller.server.start_client_match(
                parts[1].upper(),
                parts[2].upper(),
                size=controller.size,
                time_limit=controller.time_limit_per_move,
            )
            controller._handle_network_notification(result)
        return True

    if cmd == "accept":
        if controller.client.connected:
            controller.client.send("ACCEPT")
            controller.cli.msg(translator("Invitation response sent."))
        elif controller.server.running:
            result = controller.server.respond_to_invitation(
                controller.server.host_player_id, accepted=True
            )
            controller._handle_network_notification(result)
        else:
            controller.cli.msg(translator("Not connected to a server."))
        return True

    if cmd == "decline":
        if controller.client.connected:
            controller.client.send("DECLINE")
            controller.cli.msg(translator("Invitation response sent."))
        elif controller.server.running:
            result = controller.server.respond_to_invitation(
                controller.server.host_player_id, accepted=False
            )
            controller._handle_network_notification(result)
        else:
            controller.cli.msg(translator("Not connected to a server."))
        return True

    if cmd == "cancel":
        if controller.client.connected:
            controller.client.send("CANCEL")
            controller.cli.msg(translator("Cancellation request sent."))
        elif controller.server.running:
            result = controller.server.cancel_invitation(
                controller.server.host_player_id
            )
            controller._handle_network_notification(result)
        else:
            controller.cli.msg(translator("Not connected to a server."))
        return True

    if cmd == "join":
        addr = parts[1] if len(parts) > 1 else "localhost"
        port = 12345
        if ":" in addr:
            addr, port_str = addr.split(":")
            port = int(port_str)
        err = controller.client.join(addr, port)

        if err:
            controller.cli.msg(translator(err))
        else:
            controller.cli.msg(
                translator("Connected to {addr}:{port}. Mode: CLIENT").format(
                    addr=addr, port=port
                )
            )
        return True

    if cmd == "ping":
        controller.cli.msg(translator(controller.client.ping()))
        return True

    if cmd == "status":
        controller.cli.msg(translator("\n--- NETWORK STATUS ---"))
        controller.cli.msg(translator(f"Server Running: {controller.server.running}"))
        if controller.server.running:
            controller.cli.msg(
                translator(f"  Server Inbox Size: {len(controller.server.inbox)}")
            )
            controller.cli.msg(
                translator(
                    (
                        "  Client Socket: Connected"
                        if controller.server.client_socket
                        else "  Client Socket: None"
                    )
                )
            )
        controller.cli.msg(
            translator(f"Client Connected: {controller.client.connected}")
        )
        if controller.client.connected:
            controller.cli.msg(
                translator(f"  Client Inbox Size: {len(controller.client.inbox)}")
            )
            controller.cli.msg(
                translator(
                    (
                        "  Receiver Thread: Alive"
                        if controller.client.receiver_thread
                        and controller.client.receiver_thread.is_alive()
                        else "  Receiver Thread: Down"
                    )
                )
            )
        controller.cli.msg(translator("----------------------\n"))
        return True

    return False
