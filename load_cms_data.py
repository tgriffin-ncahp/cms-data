"""Load CMS datasets into drugs_data.db.

Downloads are expected in ./data/ (use cms-data CLI or direct download).
SDU files are large (200-500MB) — loaded in chunks, filtered for NC only.
NADAC files are loaded in full.

This is a convenience wrapper around cms_data.loader.
"""

from pathlib import Path

from cms_data.loader import (
    create_indexes,
    load_enrollment,
    load_nadac,
    load_sdu,
    make_engine,
)

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = Path(__file__).parent / "drugs_data.db"
STATIC_DIR = Path(__file__).parent / "static_data"


def main():
    engine = make_engine(DB_PATH)

    files = {
        "sdud_2024.csv": ("sdu_2024", "sdu"),
        "sdud_2025.csv": ("sdu_2025", "sdu"),
        "nadac_2026.csv": ("nadac_2026", "nadac"),
        "nadac_comparison_2026.csv": ("nadac_comparison", "nadac"),
    }

    loaded_tables = {}

    for filename, (table, loader_type) in files.items():
        csv_path = DATA_DIR / filename
        if not csv_path.exists():
            print(f"SKIP: {csv_path} not found. Run download first.")
            continue

        if loader_type == "sdu":
            rows = load_sdu(
                csv_path,
                table,
                engine,
                on_progress=lambda n: print(f"  {n:,} rows...", end="\r"),
            )
        else:
            rows = load_nadac(csv_path, table, engine)

        print(f"  {table}: {rows:,} rows loaded.")
        loaded_tables[table] = loader_type

    enrollment_path = STATIC_DIR / "medicaid_enrollment.csv"
    rows = load_enrollment(enrollment_path, engine)
    if rows:
        print(f"  enrollment: {rows:,} rows loaded.")
    else:
        print(f"  SKIP: {enrollment_path} not found")

    create_indexes(engine, loaded_tables)
    print("  Indexes created.")
    print(f"\nDone. Database: {DB_PATH}")


if __name__ == "__main__":
    main()
