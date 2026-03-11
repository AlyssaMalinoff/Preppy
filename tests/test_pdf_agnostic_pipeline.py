from dinner_planner.importers.pdf_classifier import classify_lines
from dinner_planner.importers.pdf_extractor import extract_sections
from dinner_planner.importers.pdf_segmenter import segment_lines


def test_agnostic_pipeline_extracts_basic_sections():
    raw_text = """
Braised Short Ribs with Carrots
Yield:
6 servings
Ingredients:
5 lb beef short ribs
2 tbsp tomato paste
Instructions:
Step 1
Brown ribs.
Step 2
Braise until tender.
"""
    segmented = segment_lines(raw_text)
    classified = classify_lines(segmented)
    extracted = extract_sections(classified)

    assert extracted.title == "Braised Short Ribs with Carrots"
    assert extracted.servings == "6 servings"
    assert len(extracted.ingredient_lines) >= 2
    assert any("Step 1" in line for line in extracted.instruction_lines)
    assert extracted.confidence >= 0.7

