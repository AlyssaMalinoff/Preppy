from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from dinner_planner.models import IngredientRecord, ParseIssue
from dinner_planner.normalization import normalize_ingredient_line


SECTION_HEADERS = {
    "ingredients": {"ingredients", "ingredient"},
    "instructions": {"instructions", "method", "directions", "steps", "preparation"},
    "servings": {"servings", "serves", "yield"},
}


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _normalize_header(line: str) -> str:
    return line.strip().lower().rstrip(":")


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"intro": []}
    current = "intro"
    for line in lines:
        header = _normalize_header(line)
        matched_section = None
        for section_name, aliases in SECTION_HEADERS.items():
            if header in aliases:
                matched_section = section_name
                break
        if matched_section:
            current = matched_section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def parse_recipe_text(raw_text: str) -> tuple[str, str | None, str | None, list[IngredientRecord], list[ParseIssue], float]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    issues: list[ParseIssue] = []

    if not lines:
        return "Untitled Recipe", None, None, [], [ParseIssue("parse", "raw_text", "No extractable text found in PDF.")], 0.0

    title = lines[0]
    sections = _split_sections(lines[1:])

    servings = None
    if "servings" in sections and sections["servings"]:
        servings = sections["servings"][0]
    else:
        servings_match = re.search(r"\b(serves?|yield)\b[:\s]+(.+)", raw_text, re.IGNORECASE)
        if servings_match:
            servings = servings_match.group(2).strip()

    ingredient_lines = sections.get("ingredients", [])
    if not ingredient_lines:
        # Fallback heuristic: lines that start with quantity-like patterns.
        ingredient_lines = [line for line in lines if re.match(r"^\d|^\d+/\d+|^\d+\s+\d+/\d+", line)]

    ingredients = [normalize_ingredient_line(line) for line in ingredient_lines if line]

    instruction_lines = sections.get("instructions", [])
    instructions = "\n".join(instruction_lines).strip() if instruction_lines else None

    confidence = 0.2
    if title and title.lower() != "untitled recipe":
        confidence += 0.2
    if servings:
        confidence += 0.1
    if ingredients:
        confidence += 0.3
    if instructions:
        confidence += 0.2

    if not ingredient_lines:
        issues.append(ParseIssue("missing_section", "ingredients", "Could not confidently detect an ingredients section."))
    if not instructions:
        issues.append(ParseIssue("missing_section", "instructions", "Could not confidently detect an instructions section."))
    if confidence < 0.6:
        issues.append(
            ParseIssue(
                "low_confidence",
                "parse_confidence",
                "Parse confidence is below threshold.",
                snippet=f"confidence={confidence:.2f}",
            )
        )

    return title, servings, instructions, ingredients, issues, min(confidence, 1.0)

