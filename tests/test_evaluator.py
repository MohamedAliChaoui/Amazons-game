import pytest

from amazons.model.ai.evaluator import Evaluator


def test_evaluator_territory_mode(monkeypatch):
    monkeypatch.setattr(
        "amazons.model.ai.evaluator.TerritoryEvaluator.evaluate",
        lambda board, color: 11,
    )

    assert Evaluator.evaluate(object(), "W", "territory") == 11


def test_evaluator_mobility_mode(monkeypatch):
    monkeypatch.setattr(
        "amazons.model.ai.evaluator.MobilityEvaluator.evaluate",
        lambda board, color: -2,
    )

    assert Evaluator.evaluate(object(), "B", "mobility") == -2


def test_evaluator_hybrid_mode_weights_scores(monkeypatch):
    monkeypatch.setattr(
        "amazons.model.ai.evaluator.TerritoryEvaluator.evaluate",
        lambda board, color: 10,
    )
    monkeypatch.setattr(
        "amazons.model.ai.evaluator.MobilityEvaluator.evaluate",
        lambda board, color: 5,
    )

    assert Evaluator.evaluate(object(), "W", "hybrid") == 8.0


def test_evaluator_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unknown evaluator mode"):
        Evaluator.evaluate(object(), "W", "nope")
