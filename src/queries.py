"""Read-only Part 4 queries on the normalized clinical trial database.

Categorical filters ignore case. Group labels normalize response to lowercase
and sex to uppercase without changing stored values. The baseline cohort does
not restrict response or sex; only the response summary filters to yes/no. Distinct
subjects are counted within each group, not deduplicated across different groups.
"""

import sqlite3

BASELINE_COHORT = """
WITH baseline AS (
    SELECT * FROM samples
    WHERE LOWER(condition) = ? AND LOWER(sample_type) = ?
      AND LOWER(treatment) = ? AND time_from_treatment_start = ?
)
"""
BASELINE_PARAMETERS = ("melanoma", "pbmc", "miraclib", 0)


def _read_rows(connection: sqlite3.Connection, sql: str, parameters: tuple) -> list[sqlite3.Row]:
    """Leave the caller's connection, row factory and transaction unchanged."""
    cursor = connection.cursor()
    try:
        cursor.row_factory = sqlite3.Row
        return cursor.execute(sql, parameters).fetchall()
    finally:
        cursor.close()


def get_project_counts(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return project/sample_count rows for baseline melanoma/miraclib/PBMC."""
    return _read_rows(
        connection,
        BASELINE_COHORT + "SELECT project, COUNT(*) AS sample_count FROM baseline "
        "GROUP BY project ORDER BY project",
        BASELINE_PARAMETERS,
    )


def get_response_subject_counts(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Count distinct responders/non-responders, excluding NULL/other responses."""
    return _read_rows(
        connection,
        BASELINE_COHORT + "SELECT LOWER(response) AS response, "
        "COUNT(DISTINCT subject) AS subject_count FROM baseline "
        "WHERE LOWER(response) IN (?, ?) "
        "GROUP BY LOWER(response) ORDER BY LOWER(response)",
        BASELINE_PARAMETERS + ("yes", "no"),
    )


def get_sex_subject_counts(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return sex/subject_count rows with distinct subjects in each sex group."""
    return _read_rows(
        connection,
        BASELINE_COHORT + "SELECT UPPER(sex) AS sex, "
        "COUNT(DISTINCT subject) AS subject_count FROM baseline "
        "GROUP BY UPPER(sex) ORDER BY UPPER(sex)",
        BASELINE_PARAMETERS,
    )


def get_bcell_average(connection: sqlite3.Connection) -> float | None:
    """Mean raw B-cell count for baseline male melanoma responders.

    Include every treatment and sample type. Each qualifying biological sample
    contributes once; this is not an average of subject means or percentages.
    Return None when no samples qualify, distinguishing missing data from zero.
    """
    rows = _read_rows(
        connection,
        "SELECT AVG(c.count) AS bcell_average FROM samples AS s "
        "JOIN cell_counts AS c ON c.sample = s.sample "
        "WHERE LOWER(s.condition) = ? AND UPPER(s.sex) = ? "
        "AND LOWER(s.response) = ? AND s.time_from_treatment_start = ? "
        "AND c.population = ?",
        ("melanoma", "M", "yes", 0, "b_cell"),
    )
    return rows[0]["bcell_average"]


def format_bcell_average(value: float | None) -> str:
    """Display a numeric mean to two decimals, or N/A for no matching samples."""
    return "N/A" if value is None else f"{value:.2f}"
