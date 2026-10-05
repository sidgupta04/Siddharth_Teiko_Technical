"""Persist responder statistics; run with `python run_analysis.py`."""

from pathlib import Path

from src.statistics import run_analysis


def main() -> None:
    database = Path(__file__).resolve().parent / "clinical_trial.db"
    results = run_analysis(database)
    print(f"Analyzed {len(results)} populations; saved results to {database.name}")
    print("All timepoints included; repeated samples per subject limit p-value interpretation.")


if __name__ == "__main__":
    main()
