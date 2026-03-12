from dinner_planner.classification.rules import classify_recipe


def test_classify_recipe_returns_expected_shape():
    result = classify_recipe(
        title="Brothy Pasta with Chickpeas",
        ingredient_names=["orecchiette", "chickpeas", "tomato", "basil"],
        instructions="Step 1 Cook pasta. Step 2 simmer sauce.",
    )
    assert result.difficulty_level in {"easy", "medium", "hard"}
    assert result.dish_category == "general"
    assert isinstance(result.seasonality_tags, list)
    assert result.repeat_policy in {"normal", "flexible", "avoid-repeat"}
    assert 0.0 <= result.popularity_score <= 1.0

