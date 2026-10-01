import pytest

from amazons.model.color import Color


def test_color_to_code_accepts_canonical_values():
    assert Color.to_code("W") == "W"
    assert Color.to_code("B") == "B"


@pytest.mark.parametrize("value", ["white", "black", "w", "b", "", None])
def test_color_to_code_rejects_non_canonical_values(value):
    with pytest.raises(ValueError, match="Invalid color code"):
        Color.to_code(value)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("W", "W"),
        ("B", "B"),
        ("w", "W"),
        ("b", "B"),
        ("white", "W"),
        ("black", "B"),
    ],
)
def test_color_normalize_accepts_boundary_inputs(value, expected):
    assert Color.normalize(value) == expected


@pytest.mark.parametrize("value", ["Blue", "x", "", None, 1])
def test_color_normalize_rejects_unknown_values(value):
    with pytest.raises(ValueError, match="Cannot normalize color"):
        Color.normalize(value)


def test_color_to_name_returns_human_readable_names():
    assert Color.to_name("W") == "white"
    assert Color.to_name("B") == "black"


@pytest.mark.parametrize("value", ["white", "black", "", None])
def test_color_to_name_rejects_invalid_codes(value):
    with pytest.raises(ValueError, match="Invalid color code"):
        Color.to_name(value)
