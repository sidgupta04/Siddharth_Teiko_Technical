"""Validate source records without repairing malformed data.

All source columns are required. Only response may be blank (stored as NULL).
Age and cell counts are non-negative integers; time is a signed integer with
no restriction to observed timepoints. Integral numeric forms such as 7.0 are
accepted. Text values retain their original spelling and capitalization.
"""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

POPULATIONS = ("b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte")
METADATA = (
    "project", "subject", "condition", "age", "sex", "treatment",
    "response", "sample", "sample_type", "time_from_treatment_start",
)
REQUIRED_COLUMNS = METADATA + POPULATIONS
SQLITE_MIN = -(2**63)
SQLITE_MAX = 2**63 - 1


def parse_integer(value: str, column: str, line: int) -> int:
    """Parse a finite, integral value representable by SQLite INTEGER."""
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"Line {line}: {column} must be an integer") from None
    if (
        not number.is_finite()
        or number != number.to_integral_value()
        or not SQLITE_MIN <= number <= SQLITE_MAX
    ):
        raise ValueError(f"Line {line}: {column} must be a finite SQLite integer")
    return int(number)


def read_samples(path: Path) -> list[dict[str, str | int | None]]:
    """Read and validate the entire CSV before any database replacement."""
    records = []
    seen = set()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader, None)
            if not header:
                raise ValueError("CSV is empty or missing a header")
            if len(header) != len(set(header)):
                raise ValueError("Duplicate CSV column names")
            for column in REQUIRED_COLUMNS:
                if column not in header:
                    raise ValueError(f"Missing required column: {column}")
            extras = set(header) - set(REQUIRED_COLUMNS)
            if extras:
                raise ValueError(f"Unexpected columns: {', '.join(sorted(extras))}")
            for values in reader:
                line = reader.line_num
                if len(values) != len(header):
                    raise ValueError(f"Line {line}: expected {len(header)} fields, got {len(values)}")
                row = dict(zip(header, values))
                for column, value in row.items():
                    if column != "response" and not value.strip():
                        raise ValueError(f"Line {line}: missing value for {column}")
                    if value.strip() and value != value.strip():
                        raise ValueError(f"Line {line}: surrounding whitespace in {column}")
                if row["sample"] in seen:
                    raise ValueError(f"Line {line}: duplicate sample identifier: {row['sample']}")
                seen.add(row["sample"])
                for column in ("age", "time_from_treatment_start") + POPULATIONS:
                    row[column] = parse_integer(row[column], column, line)
                    if column != "time_from_treatment_start" and row[column] < 0:
                        raise ValueError(f"Line {line}: {column} must be non-negative")
                if sum(row[column] for column in POPULATIONS) == 0:
                    raise ValueError(f"Line {line}: sample {row['sample']} has zero total cell count")
                row["response"] = row["response"] if row["response"].strip() else None
                records.append(row)
        except csv.Error as error:
            raise ValueError(f"Malformed CSV near line {reader.line_num}: {error}") from error
    if not records:
        raise ValueError("CSV contains no sample records")
    return records
