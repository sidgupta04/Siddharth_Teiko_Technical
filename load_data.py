"""Load the source CSV into SQLite; run with `python load_data.py`."""

from pathlib import Path

from src.database import load_data


def main() -> None:
    root = Path(__file__).resolve().parent
    database = root / "clinical_trial.db"
    samples, counts = load_data(root / "cell-count.csv", database)
    print(f"Loaded {samples} samples")
    print(f"Loaded {counts} cell-count records")
    print(f"Created {database.name}")


if __name__ == "__main__":
    main()
