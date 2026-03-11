from dinner_planner.cli import _format_quantity


def test_format_quantity_mixed_fraction():
    assert _format_quantity(1.5) == "1 1/2"


def test_format_quantity_simple_fraction():
    assert _format_quantity(0.25) == "1/4"


def test_format_quantity_whole_number():
    assert _format_quantity(2.0) == "2"

