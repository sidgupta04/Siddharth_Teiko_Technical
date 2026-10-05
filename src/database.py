"""Build a normalized SQLite database from validated source records."""

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile

from src.validation import METADATA, POPULATIONS, read_samples

SCHEMA = """
CREATE TABLE samples (
    project TEXT NOT NULL,
    subject TEXT NOT NULL,
    condition TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (typeof(age) = 'integer' AND age >= 0),
    sex TEXT NOT NULL,
    treatment TEXT NOT NULL,
    response TEXT,
    sample TEXT PRIMARY KEY NOT NULL CHECK (length(trim(sample)) > 0),
    sample_type TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL
        CHECK (typeof(time_from_treatment_start) = 'integer')
);
CREATE TABLE cell_counts (
    sample TEXT NOT NULL REFERENCES samples(sample),
    population TEXT NOT NULL CHECK (
        population IN ('b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte')
    ),
    count INTEGER NOT NULL CHECK (typeof(count) = 'integer' AND count >= 0),
    PRIMARY KEY (sample, population)
);
"""


def load_data(csv_path: Path, database_path: Path) -> tuple[int, int]:
    """Rebuild from CSV, preserving the previous database on validation/write failure.

    Paths are injectable for isolated tests. The CLI uses repository-relative
    defaults. A temporary database in the destination directory is closed before
    atomic replacement, so an incomplete load is never published.
    """
    csv_path, database_path = Path(csv_path), Path(database_path)
    if csv_path.resolve() == database_path.resolve():
        raise ValueError("Source CSV and output database must be different files")
    records = read_samples(csv_path)
    with tempfile.NamedTemporaryFile(
        prefix=".clinical-trial-", suffix=".db", dir=database_path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with closing(sqlite3.connect(temporary_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
            with connection:
                connection.executemany(
                    "INSERT INTO samples (project, subject, condition, age, sex, "
                    "treatment, response, sample, sample_type, time_from_treatment_start) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (tuple(row[column] for column in METADATA) for row in records),
                )
                connection.executemany(
                    "INSERT INTO cell_counts (sample, population, count) VALUES (?, ?, ?)",
                    ((row["sample"], population, row[population])
                     for row in records for population in POPULATIONS),
                )
        temporary_path.replace(database_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return len(records), len(records) * len(POPULATIONS)
