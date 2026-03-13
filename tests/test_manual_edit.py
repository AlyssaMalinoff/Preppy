from __future__ import annotations

from pathlib import Path

from dinner_planner.cli import (
    _instructions_to_steps,
    _persist_recipe_edit,
    _steps_to_instruction_text,
)
from dinner_planner.normalization import normalize_ingredient_line
from dinner_planner.repository import (
    apply_recipe_edit,
    connect,
    get_ingredients,
    get_recipe,
    init_db,
    insert_recipe,
)


def _seed_recipe(conn) -> int:
    return insert_recipe(
        conn,
        title="Original Recipe",
        servings="4 servings",
        instructions="Step 1\nDo original thing.",
        source_type="pdf",
        source_path="/tmp/example.pdf",
        raw_text="raw",
        parse_confidence=0.9,
        ingredients=[normalize_ingredient_line("1 cup rice"), normalize_ingredient_line("1 tbsp oil")],
        issues=[],
    )


def test_repository_apply_recipe_edit_replaces_core_fields_and_ingredients(tmp_path: Path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    recipe_id = _seed_recipe(conn)

    apply_recipe_edit(
        conn,
        recipe_id=recipe_id,
        title="Updated Recipe",
        servings="2 servings",
        instructions="Step 1\nDo updated thing.",
        ingredients=[normalize_ingredient_line("2 cups rice"), normalize_ingredient_line("1 tsp salt")],
    )

    recipe = get_recipe(conn, recipe_id)
    ingredients = get_ingredients(conn, recipe_id)
    conn.close()

    assert recipe is not None
    assert recipe["title"] == "Updated Recipe"
    assert recipe["servings"] == "2 servings"
    assert "updated thing" in recipe["instructions"].lower()
    assert len(ingredients) == 2
    assert any(item["name_normalized"] == "rice" and item["quantity_value"] == 2.0 for item in ingredients)
    assert any(item["name_normalized"] == "salt" for item in ingredients)


def test_persist_recipe_edit_uses_normalization_path(tmp_path: Path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    recipe_id = _seed_recipe(conn)

    _persist_recipe_edit(
        conn,
        recipe_id=recipe_id,
        title="Normalization Check",
        servings="6 servings",
        instructions="Step 1\nMix ingredients.",
        ingredient_lines=[
            "1 1/2 cups chick peas",
            "2 tablespoons olive oil",
            "1 tsp salt",
        ],
        save_changes=True,
    )
    recipe = get_recipe(conn, recipe_id)
    ingredients = get_ingredients(conn, recipe_id)
    conn.close()

    assert recipe is not None
    assert recipe["title"] == "Normalization Check"
    assert len(ingredients) == 3
    assert any(item["name_normalized"] == "chickpeas" and item["quantity_value"] == 1.5 for item in ingredients)
    assert any(item["quantity_unit"] == "tbsp" for item in ingredients)


def test_instruction_step_transform_helpers():
    instructions = "Step 1\nPrep onions.\nStep 2\nCook onions and serve."
    steps = _instructions_to_steps(instructions)
    assert steps == ["Prep onions.", "Cook onions and serve."]

    rebuilt = _steps_to_instruction_text(["Prep onions.", "Cook onions and serve."])
    assert rebuilt is not None
    assert "Step 1" in rebuilt
    assert "Step 2" in rebuilt


def test_cancel_path_does_not_persist_changes(tmp_path: Path):
    conn = connect(tmp_path / "test.db")
    init_db(conn)
    recipe_id = _seed_recipe(conn)
    before = get_recipe(conn, recipe_id)
    before_ingredients = get_ingredients(conn, recipe_id)

    saved = _persist_recipe_edit(
        conn,
        recipe_id=recipe_id,
        title="Should Not Save",
        servings="1 serving",
        instructions="Step 1\nShould not persist.",
        ingredient_lines=["9 cups sugar"],
        save_changes=False,
    )

    after = get_recipe(conn, recipe_id)
    after_ingredients = get_ingredients(conn, recipe_id)
    conn.close()

    assert saved is False
    assert before is not None and after is not None
    assert before["title"] == after["title"]
    assert before["servings"] == after["servings"]
    assert len(before_ingredients) == len(after_ingredients)

