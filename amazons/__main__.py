"""Command-line entry point for the Game of Amazons."""

import argparse
import builtins
import configparser
import logging
import os
import sys
import time
from pathlib import Path

from amazons.constants import DEFAULT_SHORTCUTS
from amazons.controller.engine.game_controller import GameController
from amazons.controller.network.network_server import NetworkServer
from amazons.controller.save_load_manager import SaveLoadManager
from amazons.i18n import setup_i18n
from amazons.model.ai.iterative_deepening import IterativeDeepening
from amazons.model.ai.mcts_engine import MCTSEngine
from amazons.model.ai.minimax_engine import MinimaxEngine
from amazons.model.ai.random_engine import RandomEngine
from amazons.model.ai.utils import create_ai_engine
from amazons.model.board.move import Move
from amazons.model.color import Color


CONFIG_FILE = Path.home() / ".amazonsrc"
DEFAULT_SERVER_PORT = 12345
DEFAULT_TIME_LIMIT = 30.0
DEFAULT_AI_TIME = 5.0
DEFAULT_CONTEST_DEPTH = 3
MIN_BOARD_SIZE = 4
MAX_BOARD_SIZE = 11
AI_MODES = ("minimax", "iterative", "mcts", "random")
AI_SCORING_MODES = ("territory", "mobility", "hybrid")
MCTS_SELECTION_MODES = ("UCT", "ML")
DEFAULT_CONFIG_VALUES = {
    "size": "10",
    "time": str(DEFAULT_TIME_LIMIT),
    "ai_time": str(DEFAULT_AI_TIME),
    "ai_mode": "minimax",
    "ai_minimax_scoring": "hybrid",
    "ai_mcts_selection": "UCT",
    "verbose": "false",
    "debug": "false",
    "blitz": "false",
    "gui": "false",
}
FLOAT_DEFAULT_KEYS = {"time", "ai_time"}
STRING_DEFAULT_KEYS = {
    "ai_mode",
    "ai_minimax_scoring",
    "ai_mcts_selection",
    "contest",
}
BOOLEAN_DEFAULT_KEYS = {"verbose", "debug", "blitz", "gui"}


def _(message: str) -> str:
    """Translate *message* with the globally installed gettext function."""
    return getattr(builtins, "_", lambda value: value)(message)


def write_default_config() -> None:
    """Create a default user configuration file."""
    config = configparser.ConfigParser()
    config["defaults"] = DEFAULT_CONFIG_VALUES
    config["shortcuts"] = DEFAULT_SHORTCUTS
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        config.write(handle)


def _parse_default_value(
    config: configparser.ConfigParser, key: str, value: str
):
    """Convert a stored config value to its runtime type."""
    if key == "size":
        return int(value)
    if key in FLOAT_DEFAULT_KEYS:
        return float(value)
    if key in STRING_DEFAULT_KEYS:
        return value
    if key in BOOLEAN_DEFAULT_KEYS:
        return config.getboolean("defaults", key)
    return None


def load_config():
    """Load user defaults from ``~/.amazonsrc`` if available."""
    if not CONFIG_FILE.exists():
        try:
            write_default_config()
        except OSError:
            pass
        return {}

    config = configparser.ConfigParser()
    try:
        config.read(CONFIG_FILE, encoding="utf-8")
        if "defaults" not in config:
            return {}

        defaults = {}
        for key, value in config["defaults"].items():
            parsed = _parse_default_value(config, key, value)
            if parsed is not None:
                defaults[key] = parsed
        return defaults
    except (configparser.Error, ValueError) as exc:
        print(
            f"Warning: Configuration file {CONFIG_FILE} is invalid -> {exc}"
        )
        return {}


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure application logging."""
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    log_format = (
        "%(levelname)s [%(name)s]: %(message)s"
        if debug
        else "%(levelname)s: %(message)s"
    )
    logging.basicConfig(level=level, format=log_format, stream=sys.stderr)


def build_parser(defaults_cfg):
    """Build the command-line parser for the application."""
    parser = argparse.ArgumentParser(
        prog="amazons",
        description="Game of the Amazons",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%(prog)s 1.0",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Accroit la verbosite du programme",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Affiche les messages de debug",
    )
    parser.add_argument(
        "-d",
        "--daemon",
        action="store_true",
        help="Lance le serveur en mode headless (sans interface)",
    )
    parser.add_argument(
        "-s",
        "--server",
        type=int,
        nargs="?",
        const=DEFAULT_SERVER_PORT,
        help="Lance directement en mode serveur sur le port indiqué",
    )
    parser.add_argument(
        "-b",
        "--blitz",
        action="store_true",
        help="Lance une partie en mode blitz",
    )
    parser.add_argument(
        "-t",
        "--time",
        type=float,
        default=DEFAULT_TIME_LIMIT,
        help="Limite de temps en minutes (mode blitz)",
    )
    parser.add_argument(
        "-c",
        "--contest",
        type=str,
        help="Fichier contenant une position pour le mode contest",
    )
    parser.add_argument(
        "-g",
        "--gui",
        action="store_true",
        help="Lance l'interface graphique",
    )
    parser.add_argument(
        "-a",
        "--ai",
        nargs="?",
        const="default",
        type=str,
        help="Remplace un joueur par une IA (couleur optionnelle)",
    )
    parser.add_argument(
        "-n",
        "--size",
        type=int,
        default=10,
        help=f"Taille du plateau ({MIN_BOARD_SIZE}-{MAX_BOARD_SIZE})",
    )
    parser.add_argument(
        "--ai-time",
        type=float,
        default=DEFAULT_AI_TIME,
        help="Temps de reflexion max de l'IA (en secondes)",
    )
    parser.add_argument(
        "--ai-mode",
        type=str,
        choices=AI_MODES,
        default="minimax",
        help="Algorithme d'exploration de l'IA",
    )
    parser.add_argument(
        "--ai-minimax-scoring",
        type=str,
        default="hybrid",
        help="Fonction d'evaluation (territory, mobility, hybrid)",
    )
    parser.add_argument(
        "--ai-minimax-depth",
        type=int,
        default=None,
        help="Profondeur maximale de recherche",
    )
    parser.add_argument(
        "--ai-mcts-selection",
        type=str,
        choices=MCTS_SELECTION_MODES,
        default="UCT",
        help="Fonction de selection pour MCTS",
    )
    parser.add_argument(
        "save_file",
        nargs="?",
        type=str,
        help="Fichier de sauvegarde pour restaurer une partie",
    )
    if defaults_cfg:
        parser.set_defaults(**defaults_cfg)
    return parser


def validate_args(args) -> bool:
    """Validate CLI arguments and print user-facing warnings/errors."""
    if not MIN_BOARD_SIZE <= args.size <= MAX_BOARD_SIZE:
        print(
            _(
                "Error: size must be between {min_size} and {max_size}."
            ).format(
                min_size=MIN_BOARD_SIZE,
                max_size=MAX_BOARD_SIZE,
            ),
            file=sys.stderr,
        )
        return False

    if args.time != DEFAULT_TIME_LIMIT and not args.blitz:
        print(
            _(
                "Warning: --time (-t) option requires --blitz (-b) mode "
                "to take effect."
            ),
            file=sys.stderr,
        )
    return True


def create_controller(args) -> GameController:
    """Create the main game controller from parsed arguments."""
    return GameController(
        size=args.size,
        time_limit_min=args.time,
        ai_mode=args.ai_mode,
        ai_time=args.ai_time,
        ai_depth=args.ai_minimax_depth,
        ai_evaluator=args.ai_minimax_scoring,
        use_gui=args.gui,
    )


def build_ai_engine(args):
    """Build the AI engine requested by the CLI arguments."""
    if args.ai_mode == "random":
        return RandomEngine()
    if args.ai_mode == "mcts":
        return MCTSEngine(
            time_limit=args.ai_time or DEFAULT_AI_TIME,
            selection=getattr(args, "ai_mcts_selection", None) or "UCT",
        )
    if args.ai_mode == "iterative":
        return IterativeDeepening(
            evaluator=args.ai_minimax_scoring or "hybrid",
            time_limit=args.ai_time or DEFAULT_AI_TIME,
        )
    return MinimaxEngine(
        depth=args.ai_minimax_depth or DEFAULT_CONTEST_DEPTH,
        evaluator=args.ai_minimax_scoring or "hybrid",
        time_limit=args.ai_time or DEFAULT_AI_TIME,
    )


def format_move(move, size: int) -> str:
    """Format a move as ``start-end/arrow`` in algebraic notation."""
    start = Move.to_algebraic(move.start_pos, size)
    end = Move.to_algebraic(move.end_pos, size)
    arrow = Move.to_algebraic(move.arrow_pos, size)
    return f"{start}-{end}/{arrow}"


def start_requested_server(args) -> None:
    """Start the network server if ``--server`` or ``--daemon`` was requested."""
    if args.server is None and not args.daemon:
        return

    port = args.server if args.server is not None else DEFAULT_SERVER_PORT
    server = NetworkServer()
    error = server.start(port=port)
    if error:
        print(_(error), file=sys.stderr)
        sys.exit(1)

    if not args.daemon:
        print(
            _(
                "Server started in background on port {port}."
            ).format(port=port)
        )
        return

    print(_("Daemon server is running. Press Ctrl+C to stop."))
    try:
        while server.running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    sys.exit(0)


def run_contest(args) -> int:
    """Load a contest position, compute the best move, and print it."""
    controller = create_controller(args)
    success, message = SaveLoadManager.load_game(
        controller, args.contest, skip_checksum=True
    )
    if not success:
        print(message, file=sys.stderr)
        return 1

    color = Color.W if not len(controller.history) % 2 else Color.B
    move = build_ai_engine(args).best_move(controller.board, color)
    if move is None:
        print(_("No legal move available."), file=sys.stderr)
        return 1

    print(format_move(move, controller.size))
    return 0


def load_saved_game(controller: GameController, filepath: str) -> bool:
    """Load a saved game into *controller* and mark it as restored."""
    success, message = SaveLoadManager.load_game(controller, filepath)
    print(_(message))
    if not success:
        return False
    controller.is_loaded_from_save = True
    return True


def configure_i18n_from_environment() -> None:
    """Install gettext using the current environment language settings."""
    env_lc_all = os.environ.pop("LC_ALL", None)
    env_lang = os.environ.pop("LANG", None)
    builtins._ = setup_i18n(lc_all=env_lc_all, lang=env_lang)


def main(argv=None):
    """Run the Amazons CLI entry point."""
    defaults_cfg = load_config()
    parser = build_parser(defaults_cfg)
    args = parser.parse_args(argv)

    configure_i18n_from_environment()
    setup_logging(verbose=args.verbose, debug=args.debug)

    start_requested_server(args)
    if not validate_args(args):
        return

    if args.contest:
        sys.exit(run_contest(args))

    controller = create_controller(args)
    if args.save_file and not load_saved_game(controller, args.save_file):
        return
    controller.start()


if __name__ == "__main__":
    main()
