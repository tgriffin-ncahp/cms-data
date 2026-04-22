"""Data loading functions for CMS datasets into SQLite.

Extracted from load_cms_data.py for reuse by the CLI `update` command.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

SDU_NUMERIC_COLS = [
    "Units Reimbursed",
    "Number of Prescriptions",
    "Total Amount Reimbursed",
    "Medicaid Amount Reimbursed",
    "Non Medicaid Amount Reimbursed",
]


def make_engine(db_path: Path) -> Engine:
    """Create a SQLAlchemy engine for the given SQLite database path."""
    return create_engine(f"sqlite:///{db_path}")


def load_sdu(
    csv_path: Path,
    table_name: str,
    engine: Engine,
    state_filter: str = "NC",
    chunksize: int = 50_000,
    on_progress: callable = None,
) -> int:
    """Load State Drug Utilization CSV, filtering by state.

    Args:
        csv_path: Path to the SDU CSV file.
        table_name: Target SQLite table name.
        engine: SQLAlchemy engine.
        state_filter: Two-letter state code to filter by.
        chunksize: Rows per chunk for streaming load.
        on_progress: Optional callback(total_rows) called after each chunk.

    Returns:
        Total number of rows loaded.
    """
    total_rows = 0
    first_chunk = True

    for chunk in pd.read_csv(csv_path, chunksize=chunksize, dtype=str):
        filtered = chunk[chunk["State"] == state_filter].copy()
        if filtered.empty:
            continue

        for col in SDU_NUMERIC_COLS:
            if col in filtered.columns:
                filtered[col] = pd.to_numeric(filtered[col], errors="coerce")

        filtered["Year"] = pd.to_numeric(filtered["Year"], errors="coerce")
        filtered["Quarter"] = pd.to_numeric(filtered["Quarter"], errors="coerce")

        mode = "replace" if first_chunk else "append"
        filtered.to_sql(table_name, engine, if_exists=mode, index=False)
        total_rows += len(filtered)
        first_chunk = False

        if on_progress:
            on_progress(total_rows)

    return total_rows


def load_nadac(csv_path: Path, table_name: str, engine: Engine) -> int:
    """Load NADAC CSV in full.

    Args:
        csv_path: Path to the NADAC CSV file.
        table_name: Target SQLite table name.
        engine: SQLAlchemy engine.

    Returns:
        Total number of rows loaded.
    """
    df = pd.read_csv(csv_path, dtype=str)

    for col in [
        "NADAC Per Unit",
        "Old NADAC Per Unit",
        "New NADAC Per Unit",
        "Corresponding Generic Drug NADAC Per Unit",
        "Percent Change",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.to_sql(table_name, engine, if_exists="replace", index=False)
    return len(df)


def load_enrollment(csv_path: Path, engine: Engine) -> int:
    """Load static enrollment data.

    Args:
        csv_path: Path to the enrollment CSV file.
        engine: SQLAlchemy engine.

    Returns:
        Total number of rows loaded, or 0 if file not found.
    """
    if not csv_path.exists():
        return 0
    df = pd.read_csv(csv_path)
    df.to_sql("enrollment", engine, if_exists="replace", index=False)
    return len(df)


def create_indexes(engine: Engine, tables: dict[str, str]) -> None:
    """Create indexes for common query patterns.

    Args:
        engine: SQLAlchemy engine.
        tables: Mapping of table_name -> loader_type ("sdu" or "nadac").
    """
    index_sql = []
    for table_name, loader_type in tables.items():
        if loader_type == "sdu":
            index_sql.append(
                f'CREATE INDEX IF NOT EXISTS idx_{table_name}_product ON "{table_name}"("Product Name")'
            )
            index_sql.append(
                f'CREATE INDEX IF NOT EXISTS idx_{table_name}_ndc ON "{table_name}"(NDC)'
            )
        elif loader_type == "nadac":
            index_sql.append(
                f'CREATE INDEX IF NOT EXISTS idx_{table_name}_ndc ON "{table_name}"(NDC)'
            )
            if "comparison" not in table_name:
                index_sql.append(
                    f'CREATE INDEX IF NOT EXISTS idx_{table_name}_desc ON "{table_name}"("NDC Description")'
                )

    with engine.connect() as conn:
        for sql in index_sql:
            conn.execute(text(sql))
        conn.commit()
