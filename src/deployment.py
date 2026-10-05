"""Deployment-only database bootstrap helpers."""

from collections.abc import Mapping
import os
from pathlib import Path

from src.database import load_data
from src.statistics import run_analysis


def is_streamlit_cloud(environ: Mapping[str, str] | None = None) -> bool:
    """Return true only for explicit/known Streamlit Community Cloud markers.

    Local Streamlit runs do not set these markers, so a missing local database
    continues to produce the normal ``make pipeline`` instruction. The USER
    fallback matches the Community Cloud runtime account; callers can override
    the environment mapping in tests.
    """
    environment = os.environ if environ is None else environ
    truthy = {"1", "true", "yes", "on"}
    if environment.get("STREAMLIT_RUNTIME_ENV", "").strip().lower() == "cloud":
        return True
    for key in ("STREAMLIT_CLOUD", "IS_STREAMLIT_CLOUD", "STREAMLIT_SHARING_MODE"):
        if environment.get(key, "").strip().lower() in truthy:
            return True
    return environment.get("USER", "") == "appuser"


def bootstrap_database(database_path: Path, csv_path: Path) -> bool:
    """Build the ignored database and persisted analysis once when absent.

    Return true when a database was created and false when it already existed.
    This function is intentionally explicit; the app decides whether deployment
    bootstrap is permitted before calling it.
    """
    database_path, csv_path = Path(database_path), Path(csv_path)
    if database_path.exists():
        return False
    load_data(csv_path, database_path)
    run_analysis(database_path)
    return True
