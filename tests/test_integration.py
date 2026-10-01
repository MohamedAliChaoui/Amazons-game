import os
from amazons.controller.engine.game_controller import GameController


def test_full_interactive_session(monkeypatch, tmp_path):
    gc = GameController(size=4)

    save_file = os.path.join(tmp_path, "save.amz")

    inputs = [
        "new hu",  # Command to start game
        "Ali,C",  # P1 Name
        "HAMID,D",  # P2 Name 
        "show",  # Print board
        "help",  # Print help
        "history",  # Print history
        "undo",  # Nothing to undo
        "redo",  # Nothing to redo
        "choice d1",  # Valid choice for Queen (4x4)
        "move d1-d4/d3",  # Valid move for W
        "undo",  # Undo the move
        "y",  # Bob agrees to undo
        "redo",  # Redo the move
        f"save {save_file}",  # Save game
        f"load {save_file}",  # Load game
        "move a4-a3/a4",  # B moves
        "quit",  # Ask to quit
        "n",  # Say no to saving
    ]

    def mock_input(*args, **kwargs):
        if inputs:
            return inputs.pop(0)
        raise StopIteration("End of inputs")

    monkeypatch.setattr(gc, "_get_input_or_network", mock_input)
    monkeypatch.setattr(gc.cli, "input_cli", mock_input)
    import builtins

    monkeypatch.setattr(builtins, "input", mock_input)

    try:
        gc.start()
    except StopIteration:
        pass

    assert len(inputs) == 0, f"Unconsumed inputs remaining: {inputs}"
    assert os.path.exists(save_file)


def test_new_game_then_quit_does_not_fall_back_to_unknown_command(monkeypatch):
    gc = GameController(size=4)
    outputs = []
    inputs = [
        "new hu",
        "ad",
        "hdh",
        "quit",
        "quit",
    ]

    def mock_input(*args, **kwargs):
        if inputs:
            return inputs.pop(0)
        raise StopIteration("End of inputs")

    monkeypatch.setattr(gc, "_get_input_or_network", mock_input)
    monkeypatch.setattr(gc.cli, "input_cli", mock_input)
    monkeypatch.setattr(gc.cli, "msg", lambda text: outputs.append(text))
    import builtins

    monkeypatch.setattr(builtins, "input", mock_input)

    try:
        gc.start()
    except StopIteration:
        pass

    assert not any("Unknown command" in msg for msg in outputs)
