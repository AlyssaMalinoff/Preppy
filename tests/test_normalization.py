from dinner_planner.normalization import normalize_ingredient_line


def test_normalize_basic_unit_alias():
    result = normalize_ingredient_line("2 tablespoons olive oil")
    assert result.quantity_value == 2.0
    assert result.quantity_unit == "tbsp"
    assert result.name_normalized == "olive oil"


def test_normalize_fraction_quantity():
    result = normalize_ingredient_line("1 1/2 cups chick peas")
    assert result.quantity_value == 1.5
    assert result.quantity_unit == "cup"
    assert result.name_normalized == "chickpeas"

