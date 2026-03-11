from dinner_planner.importers.pdf_extractor import ExtractedSections
from dinner_planner.importers.pdf_postprocess import (
    build_recipe_buckets,
    flatten_ingredient_lines_for_storage,
)


def test_postprocess_builds_main_and_garnish_buckets():
    extracted = ExtractedSections(
        title="Brothy Pasta with Chickpeas",
        servings="4 servings",
        ingredient_lines=[
            "3 tablespoons finely grated parmesan, plus more for serving freshly ground black pepper",
            "1 can chickpeas, drained, rinsed",
        ],
        instruction_lines=["Step 1", "Cook chickpeas."],
        confidence=0.9,
        issues=[],
    )
    buckets = build_recipe_buckets(extracted)

    assert buckets.title == "Brothy Pasta with Chickpeas"
    assert buckets.servings == "4 servings"
    assert any("chickpeas" in line for line in buckets.main_ingredient_lines)
    assert any("for serving" in line.lower() for line in buckets.garnish_lines)
    assert any("black pepper" in line.lower() for line in buckets.garnish_lines)


def test_flatten_maintains_storage_compatibility():
    extracted = ExtractedSections(
        title="Test Recipe",
        servings=None,
        ingredient_lines=[
            "1 tbsp olive oil",
            "2 tbsp parsley, for serving",
        ],
        instruction_lines=["Step 1", "Do thing."],
        confidence=0.8,
        issues=[],
    )
    buckets = build_recipe_buckets(extracted)
    flattened = flatten_ingredient_lines_for_storage(buckets)

    assert len(flattened) == len(buckets.main_ingredient_lines) + len(buckets.garnish_lines)
    assert any("olive oil" in line for line in flattened)
    assert any("serving" in line.lower() for line in flattened)


def test_nutrition_meta_is_omitted_and_reported_with_macro_hooks():
    extracted = ExtractedSections(
        title="Thai Beef with Basil",
        servings="6 servings",
        ingredient_lines=[
            "1 lb ground beef",
            "12 g fat",
            "2 g fiber",
        ],
        instruction_lines=[
            "Step 1",
            "Cook beef.",
            "Nutrition Per Serving",
            "Per serving: 240 calories",
        ],
        confidence=0.85,
        issues=[],
        nutrition_meta_lines=[
            "Nutrition Per Serving",
            "Per serving: 240 calories",
            "12 g fat",
            "2 g fiber",
        ],
    )
    buckets = build_recipe_buckets(extracted)
    flattened = flatten_ingredient_lines_for_storage(buckets)

    assert all("g fat" not in line.lower() for line in flattened)
    assert all("g fiber" not in line.lower() for line in flattened)
    assert all("nutrition per serving" not in line.lower() for line in buckets.instruction_lines)
    assert any(issue.issue_type == "omitted_meta" and issue.field_name == "nutrition_meta" for issue in buckets.issues)
    assert any("calories" in line.lower() for line in buckets.macro_hint_lines)

