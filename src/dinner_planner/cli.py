from __future__ import annotations

import json
from fractions import Fraction
from datetime import date, datetime
from pathlib import Path

import typer

from dinner_planner.classification.rules import classify_recipe
from dinner_planner.importers.pdf_importer import extract_pdf_text, parse_recipe_text
from dinner_planner.planner.generator import generate_weekly_plan
from dinner_planner.planner.models import PlannerRecipe
from dinner_planner.repository import (
    connect,
    get_ingredient_names,
    get_ingredients,
    get_recipe,
    init_db,
    insert_recipe,
    list_planner_candidates,
    list_recipes_for_classification,
    list_pending_issues,
    list_recipes,
    update_recipe_classification,
)

app = typer.Typer(help="Preppy CLI")
recipe_app = typer.Typer(help="Recipe warehouse commands")
plan_app = typer.Typer(help="Meal planner commands")
app.add_typer(recipe_app, name="recipe")
app.add_typer(plan_app, name="plan")

DEFAULT_DB = Path("data/recipes.db")


def _init_connection(db: Path):
    conn = connect(db)
    init_db(conn)
    return conn


def _format_quantity(value: float) -> str:
    # Render quantity values in kitchen-friendly mixed fractions.
    frac = Fraction(value).limit_denominator(16)
    whole = frac.numerator // frac.denominator
    remainder = frac.numerator % frac.denominator
    if remainder == 0:
        return str(whole)
    if whole == 0:
        return f"{remainder}/{frac.denominator}"
    return f"{whole} {remainder}/{frac.denominator}"


@app.command("init-db")
def init_db_command(
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
) -> None:
    conn = connect(db)
    init_db(conn)
    conn.close()
    typer.echo(f"Initialized database at {db}")


@recipe_app.command("import-pdf")
def import_pdf(
    path: Path | None = typer.Argument(None, help="Path to a single PDF file"),
    from_folder: Path | None = typer.Option(None, "--from-folder", help="Folder containing PDFs"),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
) -> None:
    if path is None and from_folder is None:
        raise typer.BadParameter("Provide a PDF path or --from-folder.")
    if path is not None and from_folder is not None:
        raise typer.BadParameter("Use either a single path or --from-folder, not both.")

    conn = _init_connection(db)
    imported = 0

    if path is not None:
        imported += _import_single_pdf(conn, path)
    elif from_folder is not None:
        pdf_files = sorted(from_folder.glob("*.pdf"))
        for pdf_path in pdf_files:
            imported += _import_single_pdf(conn, pdf_path)

    conn.close()
    typer.echo(f"Imported {imported} recipe(s).")


def _import_single_pdf(conn, path: Path) -> int:
    if not path.exists() or path.suffix.lower() != ".pdf":
        typer.echo(f"Skipping non-PDF path: {path}")
        return 0

    raw_text = extract_pdf_text(path)
    title, servings, instructions, ingredients, issues, confidence = parse_recipe_text(raw_text)
    recipe_id = insert_recipe(
        conn,
        title=title,
        servings=servings,
        instructions=instructions,
        source_type="pdf",
        source_path=str(path),
        raw_text=raw_text,
        parse_confidence=confidence,
        ingredients=ingredients,
        issues=issues,
    )
    typer.echo(f"[#{recipe_id}] {title} (confidence={confidence:.2f}, issues={len(issues)})")
    return 1


@recipe_app.command("list")
def recipe_list(
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
) -> None:
    conn = _init_connection(db)
    rows = list_recipes(conn)
    conn.close()
    if not rows:
        typer.echo("No recipes found.")
        return
    for row in rows:
        typer.echo(
            f"{row['id']}: {row['title']} | {row['status']} | conf={row['parse_confidence']:.2f} | {row['source_type']} | {row['source_path']}"
        )


@recipe_app.command("show")
def recipe_show(
    recipe_id: int = typer.Argument(..., help="Recipe ID"),
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
) -> None:
    conn = _init_connection(db)
    recipe = get_recipe(conn, recipe_id)
    if recipe is None:
        conn.close()
        typer.echo(f"Recipe {recipe_id} not found.")
        raise typer.Exit(code=1)
    ingredients = get_ingredients(conn, recipe_id)
    conn.close()

    typer.echo(f"Recipe #{recipe['id']}: {recipe['title']}")
    typer.echo(f"Servings: {recipe['servings'] or '-'}")
    typer.echo(f"Status: {recipe['status']} | confidence={recipe['parse_confidence']:.2f}")
    typer.echo(f"Source: {recipe['source_type']} ({recipe['source_path'] or '-'})")
    typer.echo("Ingredients:")
    for item in ingredients:
        qty = item["quantity_value"]
        unit = item["quantity_unit"] or ""
        qty_text = f"{_format_quantity(qty)} {unit}".strip() if qty is not None else ""
        name = (item["name_normalized"] or "").strip()
        if qty_text:
            typer.echo(f"  - {qty_text} {name}".strip())
        else:
            typer.echo(f"  - {name}".strip())
    typer.echo("Instructions:")
    typer.echo(recipe["instructions"] or "(none parsed)")


@recipe_app.command("review-pending")
def review_pending(
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
) -> None:
    conn = _init_connection(db)
    issues = list_pending_issues(conn)
    conn.close()

    if not issues:
        typer.echo("No pending parse issues.")
        return

    for issue in issues:
        typer.echo(
            f"[issue #{issue['id']}] recipe #{issue['recipe_id']} ({issue['title']}): "
            f"{issue['issue_type']} on {issue['field_name']} - {issue['message']}"
        )
        if issue["snippet"]:
            typer.echo(f"  snippet: {issue['snippet']}")


@recipe_app.command("classify-recipes")
def classify_recipes(
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
) -> None:
    conn = _init_connection(db)
    rows = list_recipes_for_classification(conn)
    count = 0
    for row in rows:
        ingredient_names = get_ingredient_names(conn, int(row["id"]))
        result = classify_recipe(
            title=row["title"],
            ingredient_names=ingredient_names,
            instructions=row["instructions"],
        )
        update_recipe_classification(
            conn,
            recipe_id=int(row["id"]),
            difficulty_level=result.difficulty_level,
            dish_category=result.dish_category,
            seasonality_tags=result.seasonality_tags,
            repeat_policy=result.repeat_policy,
            popularity_score=result.popularity_score,
        )
        count += 1
    conn.close()
    typer.echo(f"Classified {count} recipe(s).")


def _build_planner_recipes(conn) -> list[PlannerRecipe]:
    candidates = list_planner_candidates(conn)
    planner_recipes: list[PlannerRecipe] = []
    for row in candidates:
        recipe_id = int(row["id"])
        seasonality_raw = row["seasonality_tags"]
        seasonality_tags = ["all"]
        if seasonality_raw:
            try:
                parsed = json.loads(seasonality_raw)
                if isinstance(parsed, list) and parsed:
                    seasonality_tags = [str(tag) for tag in parsed]
            except json.JSONDecodeError:
                seasonality_tags = ["all"]
        planner_recipes.append(
            PlannerRecipe(
                recipe_id=recipe_id,
                title=row["title"],
                difficulty_level=row["difficulty_level"] or "medium",
                dish_category=row["dish_category"] or "general",
                seasonality_tags=seasonality_tags,
                repeat_policy=row["repeat_policy"] or "normal",
                popularity_score=float(row["popularity_score"] or 0.5),
                ingredient_names=get_ingredient_names(conn, recipe_id),
            )
        )
    return planner_recipes


@plan_app.command("week")
def plan_week(
    db: Path = typer.Option(DEFAULT_DB, "--db", help="SQLite DB path"),
    start_date: str | None = typer.Option(None, "--start-date", help="Start date (YYYY-MM-DD). Defaults to today."),
    output_dir: Path = typer.Option(Path("output/plans"), "--output-dir", help="Directory for plan outputs."),
) -> None:
    conn = _init_connection(db)
    planner_recipes = _build_planner_recipes(conn)
    conn.close()
    if not planner_recipes:
        typer.echo("No recipes available to plan.")
        raise typer.Exit(code=1)

    start_day = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date.today()
    plan = generate_weekly_plan(planner_recipes, start_day)

    typer.echo(f"Weekly plan starting {plan.start_day.isoformat()}:")
    for idx, day_plan in enumerate(plan.days, start=1):
        why = ", ".join(day_plan.reasons[:3])
        typer.echo(f"{idx}. {day_plan.day.isoformat()} - {day_plan.title} (score={day_plan.score:.2f}; {why})")

    iso_year, iso_week, _ = plan.start_day.isocalendar()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{iso_year}-W{iso_week:02d}.plan.json"
    md_path = output_dir / f"{iso_year}-W{iso_week:02d}.plan.md"

    json_payload = {
        "start_day": plan.start_day.isoformat(),
        "days": [
            {
                "day": item.day.isoformat(),
                "recipe_id": item.recipe_id,
                "title": item.title,
                "score": item.score,
                "reasons": item.reasons,
            }
            for item in plan.days
        ],
    }
    json_path.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

    lines = [f"# Weekly Plan ({plan.start_day.isoformat()})", ""]
    for item in plan.days:
        lines.append(f"- **{item.day.isoformat()}**: {item.title} (`#{item.recipe_id}`)")
        lines.append(f"  - Score: {item.score:.2f}")
        lines.append(f"  - Why: {', '.join(item.reasons[:3])}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    typer.echo(f"Saved plan to {md_path} and {json_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

