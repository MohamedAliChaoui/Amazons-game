# Amazons

Python implementation of the Game of Amazons with a bitboard-based game
engine, an interactive command-line interface, and multiple AI engines.

## Features

- Variable board size from 4x4 to 11x11
- Human vs human, human vs AI, and (AI vs AI in the CLI to analyse the diffrence beetween them ) 
- AI engines: `random`, `minimax`, `iterative`, `mcts`
- Algebraic move notation such as `e2-e4/e6`
- Board display, move history, time display, and configuration display
- Undo support for human turns
- Automated test suite with `pytest`
- **Interactive Web Demo** (WebAssembly / Pyodide) ready for portfolio showcase

## Interactive Web Demo (Portfolio)

A browser-ready version is located in the `web/` directory. It runs the Python engine and AI directly in the browser via Pyodide (WebAssembly) with zero backend server required:

```powershell
# Test locally
python -m http.server 8000 --directory web
```
Then open `http://localhost:8000/`.

## Requirements

- Python 3.10 or newer
- `pip`

## Installation

Install the project in editable mode:

```powershell
python -m pip install -e .
```

After installation, the project can be launched with either:

```powershell
amazons
```

or:

```powershell
python -m amazons
```

## Launching the Game

Show startup options:

```powershell
amazons -h
```

Start the default CLI:

```powershell
amazons
python -m amazons
```

Start with custom AI settings:

```powershell
amazons --ai-mode mcts --ai-time 3
```

Start with a smaller board:

```powershell
amazons --size 6
```

## CLI Commands

Inside the interactive shell, the following commands are currently available:

- `new [hu|ai|aiai]`
- `show board`
- `show history`
- `show time`
- `show configuration`
- `move <from>-<to>`
- `choice <square>`
- `undo`
- `help`
- `quit`

Examples:

```text
new ai
show configuration
choice d4
move e2-e4
```

## AI Options

The project currently supports these launch-time AI options:

- `--ai-time`
- `--ai-mode`
- `--ai-minimax-scoring`
- `--ai-minimax-depth`

Available AI modes:

- `random`
- `minimax`
- `iterative`
- `mcts`

Available minimax scoring modes:

- `territory`
- `mobility`
- `hybrid`

## Tests

Run the test suite with:

```powershell
python -m pytest -q
```

If `flake8` is installed, run the style check with:

```powershell
python -m flake8 amazons tests
```

## Project Structure

```text
amazons/
  __main__.py
  controller/
  model/
  view/
tests/
pyproject.toml
README.md
```

Main directories:

- `amazons/controller`: game flow
- `amazons/model`: board, players, and AI engines
- `amazons/view`: CLI entry points
- `tests`: automated tests

## Current Status

Implemented:

- core bitboard board representation
- legal move generation and validation
- CLI shell and in-game commands
- multiple AI engines
- automated tests
- save/load game
- undo/redo support
- pause and hint features
- configuration file (.amazonsrc) support

Not fully implemented yet:

- full internationalization
- network multi-client handling and invitations

## Authors

PDP Amazons Team
