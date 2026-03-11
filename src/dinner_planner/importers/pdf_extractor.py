from __future__ import annotations

import re
from dataclasses import dataclass

from dinner_planner.importers.pdf_classifier import ClassifiedLine
from dinner_planner.models import ParseIssue


@dataclass(slots=True)
class ExtractedSections:
    title: str
    servings: str | None
    ingredient_lines: list[str]
    instruction_lines: list[str]
    confidence: float
    issues: list[ParseIssue]


def _find_first_index(items: list[ClassifiedLine], predicate) -> int | None:
    for idx, item in enumerate(items):
        if predicate(item):
            return idx
    return None


def _extract_servings(classified: list[ClassifiedLine]) -> str | None:
    for idx, item in enumerate(classified):
        lower = item.line.text.lower()
        if item.label == "servings":
            m = re.match(r"^(yield|serves?|servings?)\s*:?\s*(.+)$", item.line.text, re.IGNORECASE)
            if m and m.group(2).strip():
                return m.group(2).strip()
            if idx + 1 < len(classified):
                nxt = classified[idx + 1].line.text.strip()
                if nxt:
                    return nxt
    return None


def extract_sections(classified: list[ClassifiedLine]) -> ExtractedSections:
    issues: list[ParseIssue] = []
    if not classified:
        return ExtractedSections("Untitled Recipe", None, [], [], 0.0, [ParseIssue("parse", "raw_text", "No lines found.")])

    ingredients_header_idx = _find_first_index(
        classified,
        lambda item: item.label.startswith("header:") and item.line.text.lower() in {"ingredients", "ingredient"},
    )
    instructions_start_idx = _find_first_index(
        classified,
        lambda item: item.label.startswith("header:") and item.line.text.lower() in {"instructions", "method", "directions", "steps", "preparation"}
        or item.label == "instructions",
    )

    title = "Untitled Recipe"
    title_search_end = ingredients_header_idx if ingredients_header_idx is not None else len(classified)
    title_candidates = [c for c in classified[:title_search_end] if c.label == "title_candidate"]
    if title_candidates:
        best = max(title_candidates, key=lambda c: c.score)
        title = best.line.text
    else:
        issues.append(ParseIssue("missing_section", "title", "Could not confidently detect title."))

    servings = _extract_servings(classified)

    ingredient_lines: list[str] = []
    if ingredients_header_idx is not None:
        end_idx = instructions_start_idx if instructions_start_idx is not None else len(classified)
        for item in classified[ingredients_header_idx + 1 : end_idx]:
            if item.label == "boundary":
                break
            if item.label in {"ingredient", "other", "title_candidate"} and not item.label.startswith("header:"):
                ingredient_lines.append(item.line.text)
    else:
        ingredient_lines = [item.line.text for item in classified if item.label == "ingredient"]

    instruction_lines: list[str] = []
    if instructions_start_idx is not None:
        start_idx = instructions_start_idx
        if classified[instructions_start_idx].label.startswith("header:"):
            start_idx += 1
        for item in classified[start_idx:]:
            if item.label == "boundary":
                break
            instruction_lines.append(item.line.text)

    confidence = 0.2
    if title != "Untitled Recipe":
        confidence += 0.2
    if servings:
        confidence += 0.1
    if ingredient_lines:
        confidence += 0.3
    if instruction_lines:
        confidence += 0.2

    if not ingredient_lines:
        issues.append(ParseIssue("missing_section", "ingredients", "Could not confidently detect ingredients section."))
    if not instruction_lines:
        issues.append(ParseIssue("missing_section", "instructions", "Could not confidently detect instructions section."))

    return ExtractedSections(
        title=title,
        servings=servings,
        ingredient_lines=ingredient_lines,
        instruction_lines=instruction_lines,
        confidence=min(confidence, 1.0),
        issues=issues,
    )

