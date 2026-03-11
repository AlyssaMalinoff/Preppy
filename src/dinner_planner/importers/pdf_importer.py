from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from dinner_planner.importers.pdf_classifier import classify_lines
from dinner_planner.importers.pdf_extractor import extract_sections
from dinner_planner.importers.pdf_postprocess import (
    build_recipe_buckets,
    flatten_ingredient_lines_for_storage,
)
from dinner_planner.importers.pdf_segmenter import segment_lines
from dinner_planner.models import IngredientRecord, ParseIssue
from dinner_planner.normalization import normalize_ingredient_line

LOWERCASE_TITLE_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "vs",
}


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _normalize_title(title: str) -> str:
    repaired = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", title.strip())
    repaired = re.sub(r"\s+", " ", repaired).strip()
    words = repaired.split(" ")
    if not words:
        return "Untitled Recipe"
    out_words: list[str] = []
    for idx, word in enumerate(words):
        lowered = word.lower()
        if idx in (0, len(words) - 1):
            out_words.append(lowered.capitalize())
        elif lowered in LOWERCASE_TITLE_WORDS:
            out_words.append(lowered)
        else:
            out_words.append(lowered.capitalize())
    return " ".join(out_words)


def _parse_recipe_text_agnostic(raw_text: str) -> tuple[str, str | None, str | None, list[IngredientRecord], list[ParseIssue], float]:
    segmented = segment_lines(raw_text)
    classified = classify_lines(segmented)
    extracted = extract_sections(classified)
    buckets = build_recipe_buckets(extracted)
    ingredient_lines = flatten_ingredient_lines_for_storage(buckets)
    ingredients = [normalize_ingredient_line(line) for line in ingredient_lines if line]
    instructions = "\n".join(buckets.instruction_lines).strip() if buckets.instruction_lines else None
    title = _normalize_title(buckets.title) if buckets.title else "Untitled Recipe"
    return title, buckets.servings, instructions, ingredients, buckets.issues, buckets.confidence


def parse_recipe_text(raw_text: str) -> tuple[str, str | None, str | None, list[IngredientRecord], list[ParseIssue], float]:
    return _parse_recipe_text_agnostic(raw_text)

