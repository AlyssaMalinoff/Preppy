# Preppy (Recipe Warehouse MVP)

This project currently focuses on:

- importing recipes from text-based PDFs (single file or batch folder),
- normalizing ingredient names and units for storage,
- storing parse confidence and pending review issues.

## Quick start

1. Create and activate a virtualenv.
2. Install dependencies:
   - `pip install -e .`
3. Initialize database:
   - `preppy init-db`
4. Import one PDF:
   - `preppy recipe import-pdf /path/to/recipe.pdf`
5. Import a folder of PDFs:
   - `preppy recipe import-pdf --from-folder /path/to/folder`

## Helpful commands

- `preppy recipe list`
- `preppy recipe show <id>`
- `preppy recipe review-pending`
