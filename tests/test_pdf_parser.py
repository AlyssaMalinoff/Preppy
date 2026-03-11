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


def test_parse_recipe_text_filters_pdf_metadata_noise():
    raw_text = """
Unlock access to over 50,000+ expertly tested recipes. SUBSCRIBE TODAY »
Beef and White Bean Stew With Cumin
5/8/25, 3:31 PM Beef and White Bean Stew With Cumin Recipe | Epicurious
Ingredients:
3 lb boneless beef chuck roast
2 tbsp extra-virgin olive oil
https://www.epicurious.com/recipes/food/views/ba-syn-beef-and-white-bean-stew-with-cumin 1/3
Instructions:
Step 1
Brown beef in oil.
Tags Dinner Main
Start your free trial and get unlimited inspiration.
"""
    title, _, instructions, ingredients, issues, confidence = parse_recipe_text(raw_text)
    assert title == "Beef and White Bean Stew with Cumin"
    assert len(ingredients) == 2
    assert all("epicurious" not in item.name_normalized for item in ingredients)
    assert instructions is not None
    assert "free trial" not in instructions.lower()
    assert confidence >= 0.6
    assert any(issue.issue_type == "filtered_line" for issue in issues)


def test_parse_recipe_text_stops_on_inline_tags_and_related_markers():
    raw_text = """
Brothy Pasta with Chickpeas
Ingredients:
1 cup chickpeas
Instructions:
Step 1
Cook pasta in broth.
Tags Pasta Soup Dinner
SEE RELATED RECIPES AND COOKING TIPS
"""
    _, _, instructions, ingredients, _, _ = parse_recipe_text(raw_text)
    assert len(ingredients) == 1
    assert instructions is not None
    assert "tags pasta" not in instructions.lower()
    assert "see related recipes" not in instructions.lower()


def test_parse_recipe_text_normalizes_joined_title_words():
    raw_text = """
Beef and White Bean Stew WithCumin
Ingredients:
1 lb beef
Instructions:
Cook beef.
"""
    title, _, _, _, _, _ = parse_recipe_text(raw_text)
    assert title == "Beef and White Bean Stew with Cumin"


def test_parse_recipe_text_keeps_for_serving_ingredient_line():
    raw_text = """
Cumin Stew
Ingredients:
Steamed couscous and finely chopped parsley (for serving)
Instructions:
Serve warm.
"""
    _, _, _, ingredients, issues, _ = parse_recipe_text(raw_text)
    assert len(ingredients) == 1
    assert "couscous" in ingredients[0].name_normalized
    assert not any(
        issue.issue_type == "filtered_line" and (issue.snippet or "").lower().find("for serving") >= 0
        for issue in issues
    )


def test_parse_recipe_text_handles_yield_wrapped_ingredients_and_private_notes():
    raw_text = """
Crisp Gnocchi with Brussels Sprouts and Brown Butter
Yield:
4 servings
Ingredients:
1 lb brussels sprouts (or
other green vegetables like broccoli)
1 package shelf-stable
refrigerated potato gnocchi
Instructions:
Step 1
Cook everything together.
Private Notes
Leave a Private Note on this recipe and see it here.
"""
    title, servings, instructions, ingredients, _, _ = parse_recipe_text(raw_text)
    assert title == "Crisp Gnocchi with Brussels Sprouts and Brown Butter"
    assert servings == "4 servings"
    assert instructions is not None
    assert "private notes" not in instructions.lower()
    assert len(ingredients) == 2
    assert "other green vegetables like broccoli" in ingredients[0].name_normalized
    assert "refrigerated potato gnocchi" in ingredients[1].name_normalized


def test_title_is_picked_before_ingredients_not_from_steps():
    raw_text = """
Crisp Gnocchi with Brussels Sprouts and Brown Butter
Ingredients:
1 package gnocchi
Instructions:
Step 1
Season with salt and a generous amount of black pepper, and cook.
"""
    title, _, instructions, ingredients, _, _ = parse_recipe_text(raw_text)
    assert title == "Crisp Gnocchi with Brussels Sprouts and Brown Butter"
    assert instructions is not None
    assert len(ingredients) == 1


def test_wrapped_title_lines_are_joined():
    raw_text = """
Crisp Gnocchi
With Brussels Sprouts and Brown Butter
Ingredients:
1 package gnocchi
Instructions:
Step 1
Cook and serve.
"""
    title, _, _, _, _, _ = parse_recipe_text(raw_text)
    assert title == "Crisp Gnocchi with Brussels Sprouts and Brown Butter"


def test_for_serving_line_is_not_merged_into_previous_quantity_line():
    raw_text = """
Gnocchi
Ingredients:
1/2 tsp honey
freshly grated parmesan, for serving
Instructions:
Step 1
Serve.
"""
    _, _, _, ingredients, _, _ = parse_recipe_text(raw_text)
    assert len(ingredients) == 2
    assert "honey" in ingredients[0].name_normalized
    assert "parmesan" in ingredients[1].name_normalized


def test_nyt_descriptive_blurb_is_filtered_from_instructions():
    raw_text = """
Gnocchi with Brussels Sprouts
Ingredients:
1 package gnocchi
Instructions:
Step 1
Cook gnocchi in pan.
For a fantastic meal that can be ready in 20 minutes, toss together seared gnocchi.
The key to this recipe is how you cook store-bought gnocchi. No need to boil.
Serve hot.
"""
    _, _, instructions, _, _, _ = parse_recipe_text(raw_text)
    assert instructions is not None
    assert "fantastic meal" not in instructions.lower()
    assert "key to this recipe" not in instructions.lower()
    assert "no need to boil" not in instructions.lower()


def test_title_rejects_total_time_metadata():
    raw_text = """
Total Time 20 Minutes
Crisp Gnocchi with Brussels Sprouts and Brown Butter
Ingredients:
1 package gnocchi
Instructions:
Step 1
Cook gnocchi.
"""
    title, _, _, _, _, _ = parse_recipe_text(raw_text)
    assert title == "Crisp Gnocchi with Brussels Sprouts and Brown Butter"


def test_embedded_for_serving_garnish_line_is_split():
    raw_text = """
Crisp Gnocchi
Ingredients:
1/2 tsp honey freshly grated parmesan, for serving
Instructions:
Step 1
Serve.
"""
    _, _, _, ingredients, _, _ = parse_recipe_text(raw_text)
    assert len(ingredients) == 2
    assert "honey" in ingredients[0].name_normalized
    assert "parmesan" in ingredients[1].name_normalized


def test_for_serving_followed_by_new_ingredient_phrase_is_split():
    raw_text = """
Brothy Pasta with Chickpeas
Ingredients:
3 tablespoons finely grated parmesan, plus more for serving freshly ground black pepper
Instructions:
Step 1
Cook and serve.
"""
    _, _, _, ingredients, _, _ = parse_recipe_text(raw_text)
    names = [item.name_normalized for item in ingredients]
    assert any("parmesan" in name for name in names)
    assert any("black pepper" in name for name in names)


def test_servings_lines_inside_ingredients_are_ignored_not_flagged():
    raw_text = """
Crisp Gnocchi
With Brussels Sprouts and Brown Butter
Ingredients:
Yield:
4 servings
1 package gnocchi
Instructions:
Step 1
Cook.
"""
    title, servings, _, ingredients, issues, _ = parse_recipe_text(raw_text)
    assert title == "Crisp Gnocchi with Brussels Sprouts and Brown Butter"
    assert servings == "4 servings"
    assert len(ingredients) == 1
    assert not any(issue.issue_type == "filtered_line" for issue in issues)


def test_three_line_wrapped_title_is_joined():
    raw_text = """
Crisp Gnocchi
With Brussels
Sprouts and Brown Butter
Ingredients:
1 package gnocchi
Instructions:
Step 1
Cook.
"""
    title, _, _, _, _, _ = parse_recipe_text(raw_text)
    assert title == "Crisp Gnocchi with Brussels Sprouts and Brown Butter"


def test_nyt_byline_not_used_as_title():
    raw_text = """
Karsten Moran for the New York Times
Braised Short Ribs with Carrots
Ingredients:
1 lb short ribs
Instructions:
Step 1
Cook slowly.
"""
    title, _, _, _, _, _ = parse_recipe_text(raw_text)
    assert title == "Braised Short Ribs with Carrots"


def test_embedded_ingredient_block_is_moved_out_of_instructions():
    raw_text = """
Braised Short Ribs with Carrots
Ingredients:
5 lb short ribs
Instructions:
Step 1
Brown meat.
1 medium leek, white and tender
green parts, cut in 1-inch dice
2 tablespoons unsalted butter
Step 2
Finish braise.
"""
    _, _, instructions, ingredients, _, _ = parse_recipe_text(raw_text)
    assert instructions is not None
    assert "1 medium leek" not in instructions.lower()
    assert "2 tablespoons unsalted butter" not in instructions.lower()
    ingredient_names = [item.name_normalized for item in ingredients]
    assert any("leek" in name for name in ingredient_names)
    assert any("butter" in name for name in ingredient_names)


def test_nutrition_lines_are_omitted_and_flagged_for_review():
    raw_text = """
Thai Beef with Basil
Ingredients:
1 lb ground beef
12 g fat
2 g fiber
Instructions:
Step 1
Cook beef.
Nutrition Per Serving
Per serving: 240 calories
"""
    _, _, instructions, ingredients, issues, _ = parse_recipe_text(raw_text)
    ingredient_names = [item.name_normalized for item in ingredients]

    assert all("fat" not in name or "ground" in name for name in ingredient_names)
    assert all("fiber" not in name for name in ingredient_names)
    assert instructions is not None
    assert "nutrition per serving" not in instructions.lower()
    assert any(issue.issue_type == "omitted_meta" and issue.field_name == "nutrition_meta" for issue in issues)

