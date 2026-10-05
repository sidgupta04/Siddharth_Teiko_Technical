"""Sample-level responder comparisons using all available timepoints.

Repeated samples from the same subject are treated as independent for the literal
assignment analysis. This violates the independence assumption and limits the
interpretation of p-values; surface this limitation in the later README/dashboard.
This exploratory analysis does not establish causality or predictive performance.
"""

from contextlib import closing
import math
from pathlib import Path
import sqlite3
from statistics import median

from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests

from src.validation import POPULATIONS

STATISTICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS population_statistics (
    population TEXT PRIMARY KEY NOT NULL,
    responder_n INTEGER NOT NULL CHECK (responder_n > 0),
    non_responder_n INTEGER NOT NULL CHECK (non_responder_n > 0),
    responder_median REAL NOT NULL,
    non_responder_median REAL NOT NULL,
    u_statistic REAL NOT NULL,
    p_value REAL NOT NULL CHECK (p_value BETWEEN 0 AND 1),
    adjusted_p_value REAL NOT NULL CHECK (adjusted_p_value BETWEEN 0 AND 1),
    significant INTEGER NOT NULL CHECK (significant IN (0, 1))
)
"""


def get_responder_data(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return eligible sample percentages and metadata for analysis/boxplots.

    Match categorical values case-insensitively, preserving source data. Include
    every timepoint; response is normalized only in this query's output.
    """
    cursor = connection.cursor()
    try:
        cursor.row_factory = sqlite3.Row
        return cursor.execute(
            "SELECT f.sample, s.subject, s.time_from_treatment_start, "
            "LOWER(s.response) AS response, f.population, f.percentage "
            "FROM cell_frequencies AS f JOIN samples AS s ON s.sample = f.sample "
            "WHERE LOWER(s.condition) = ? AND LOWER(s.treatment) = ? "
            "AND LOWER(s.sample_type) = ? AND LOWER(s.response) IN (?, ?) "
            "ORDER BY f.sample, f.population",
            ("melanoma", "miraclib", "pbmc", "yes", "no"),
        ).fetchall()
    finally:
        cursor.close()


def calculate_statistics(rows: list[sqlite3.Row]) -> list[dict[str, str | int | float]]:
    """Compare percentages with responder values as the first U-test group.

    SciPy's auto method uses exact tests for small untied groups, otherwise the
    tie-corrected asymptotic test with continuity correction. Empty groups or
    invalid/incomplete frequencies fail explicitly before results are persisted.
    """
    groups = {population: {"yes": [], "no": []} for population in POPULATIONS}
    samples = {}
    for row in rows:
        sample, population, response = row["sample"], row["population"], row["response"]
        value = row["percentage"]
        if population not in groups or response not in ("yes", "no"):
            raise ValueError(f"Invalid population or response for sample {sample}")
        if value is None or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f"Invalid percentage for sample {sample}, population {population}")
        observed = samples.setdefault(sample, {})
        if population in observed:
            raise ValueError(f"Duplicate frequency for sample {sample}, population {population}")
        observed[population] = response
        groups[population][response].append(value)
    for sample, observed in samples.items():
        if set(observed) != set(POPULATIONS) or len(set(observed.values())) != 1:
            raise ValueError(f"Incomplete or inconsistent frequencies for sample {sample}")

    results = []
    for population in POPULATIONS:
        responders = groups[population]["yes"]
        non_responders = groups[population]["no"]
        if not responders or not non_responders:
            raise ValueError(f"Both response groups need at least one sample for {population}")
        test = mannwhitneyu(
            responders, non_responders, alternative="two-sided", method="auto",
            use_continuity=True,
        )
        results.append({
            "population": population,
            "responder_n": len(responders),
            "non_responder_n": len(non_responders),
            "responder_median": float(median(responders)),
            "non_responder_median": float(median(non_responders)),
            "u_statistic": float(test.statistic),
            "p_value": float(test.pvalue),
        })
    adjusted = multipletests([row["p_value"] for row in results], method="fdr_bh")[1]
    for result, p_value in zip(results, adjusted):
        result["adjusted_p_value"] = float(p_value)
        result["significant"] = int(p_value < 0.05)
    return results


def run_analysis(database_path: Path) -> list[dict[str, str | int | float]]:
    """Read a pipeline-created database and atomically replace its five results.

    The loader rebuilds the database, so rerun analysis after each load. A failed
    analysis leaves prior results untouched. Missing databases are never created.
    """
    database_path = Path(database_path).resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"Database not found: {database_path}. Run python load_data.py first.")
    with closing(sqlite3.connect(database_path.as_uri() + "?mode=rw", uri=True)) as connection:
        with connection:
            connection.execute("BEGIN")
            results = calculate_statistics(get_responder_data(connection))
            connection.execute(STATISTICS_SCHEMA)
            connection.execute("DELETE FROM population_statistics")
            connection.executemany(
                "INSERT INTO population_statistics (population, responder_n, non_responder_n, "
                "responder_median, non_responder_median, u_statistic, p_value, adjusted_p_value, significant) "
                "VALUES (:population, :responder_n, :non_responder_n, :responder_median, "
                ":non_responder_median, :u_statistic, :p_value, :adjusted_p_value, :significant)",
                results,
            )
    return results
