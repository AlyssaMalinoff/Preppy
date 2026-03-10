from __future__ import annotations

from pathlib import Path

import typer

from dinner_planner.importers.pdf_importer import extract_pdf_text, parse_recipe_text
from dinner_planner.repository import (
    connect,
    get_ingredients,
    get_recipe,
    init_db,
    insert_recipe,
    list_pending_issues,
    list_recipes,
)

app = typer.Typer(help="Preppy CLI")
recipe_app = typer.Typer(help="Recipe warehouse commands")
app.add_typer(recipe_app, name="recipe")

DEFAULT_DB = Path("data/recipes.db")


def _init_connection(db: Path):
    conn = connect(db)
    init_db(conn)
    return conn


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
        qty_text = f"{qty:g} {unit}".strip() if qty is not None else ""
        typer.echo(f"  - {qty_text} {item['name_normalized']}".strip())
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()

