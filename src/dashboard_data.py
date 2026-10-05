"""Read-only dashboard data assembly and overview filtering, without Streamlit."""

from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from src.frequencies import get_frequency_data
from src.queries import (
    get_bcell_average, get_project_counts, get_response_subject_counts,
    get_sex_subject_counts,
)
from src.statistics import get_responder_data
from src.validation import POPULATIONS


def get_statistics(connection: sqlite3.Connection) -> pd.DataFrame:
    """Read persisted results; never rerun statistical tests in the dashboard."""
    results = pd.read_sql_query(
        "SELECT population, responder_n, non_responder_n, responder_median, "
        "non_responder_median, u_statistic, p_value, adjusted_p_value, significant "
        "FROM population_statistics ORDER BY population", connection,
    )
    if len(results) != 5 or set(results["population"]) != set(POPULATIONS):
        raise ValueError("Incomplete statistics. Run `make pipeline` before starting the dashboard.")
    results["significant"] = results["significant"].astype(bool)
    return results


def load_dashboard_data(database_path: Path) -> dict:
    """Read a consistent snapshot and close the connection before returning.

    No caching: each Streamlit rerun reflects the latest completed pipeline.
    Missing/incomplete databases are errors, never an instruction to rebuild here.
    """
    path = Path(database_path).resolve()
    if not path.is_file():
        raise FileNotFoundError("Database not found. Run `make pipeline` before starting the dashboard.")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("BEGIN")
            metadata = pd.read_sql_query(
                "SELECT sample, condition, treatment, sample_type, time_from_treatment_start "
                "FROM samples ORDER BY sample", connection,
            )
            frequencies = pd.DataFrame(
                [dict(r) for r in get_frequency_data(connection)],
                columns=["sample", "total_count", "population", "count", "percentage"],
            )
            overview = frequencies.merge(metadata, on="sample", validate="many_to_one")
            responders = pd.DataFrame(
                [dict(r) for r in get_responder_data(connection)],
                columns=["sample", "subject", "time_from_treatment_start", "response", "population", "percentage"],
            )
            return {
                "total_samples": len(metadata),
                "overview": overview,
                "responders": responders,
                "statistics": get_statistics(connection),
                "project_counts": pd.DataFrame([dict(r) for r in get_project_counts(connection)], columns=["project", "sample_count"]),
                "response_counts": pd.DataFrame([dict(r) for r in get_response_subject_counts(connection)], columns=["response", "subject_count"]),
                "sex_counts": pd.DataFrame([dict(r) for r in get_sex_subject_counts(connection)], columns=["sex", "subject_count"]),
                "bcell_average": get_bcell_average(connection),
            }
    except (sqlite3.Error, pd.errors.DatabaseError) as error:
        raise ValueError("Database is unreadable or incomplete. Run `make pipeline` before starting the dashboard.") from error


def filter_frequency_data(
    data: pd.DataFrame, sample_search: str = "", condition: str | None = None,
    treatment: str | None = None, timepoint: int | None = None,
) -> pd.DataFrame:
    """Filter overview rows only; never alter the statistical/base cohorts."""
    selected = data["sample"].str.contains(sample_search, case=False, regex=False, na=False)
    if condition is not None:
        selected &= data["condition"].str.casefold() == condition.casefold()
    if treatment is not None:
        selected &= data["treatment"].str.casefold() == treatment.casefold()
    if timepoint is not None:
        selected &= data["time_from_treatment_start"] == timepoint
    return data.loc[selected].copy()
