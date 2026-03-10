from dinner_planner.importers.pdf_importer import parse_recipe_text


def test_parse_recipe_text_happy_path():
    raw_text = """
Simple Chili
Servings:
4
Ingredients:
1 lb ground beef
2 tbsp tomato paste
1 cup beans
Instructions:
Brown beef. Add tomato paste and beans. Simmer 20 minutes.
"""
    title, servings, instructions, ingredients, issues, confidence = parse_recipe_text(raw_text)
    assert title == "Simple Chili"
    assert servings == "4"
    assert instructions is not None
    assert len(ingredients) == 3
    assert confidence >= 0.6
    assert not any(issue.issue_type == "low_confidence" for issue in issues)


def test_parse_recipe_text_missing_sections_creates_issues():
    raw_text = """
Mysterious Soup
Water and herbs.
"""
    _, _, instructions, ingredients, issues, confidence = parse_recipe_text(raw_text)
    assert instructions is None
    assert ingredients == []
    assert confidence < 0.6
    assert any(issue.issue_type == "low_confidence" for issue in issues)

