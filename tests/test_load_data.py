from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from src.database import load_data

POPULATIONS = {"b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"}
ROOT = Path(__file__).resolve().parents[1]


def snapshot(path):
    with closing(sqlite3.connect(path)) as connection:
        return (
            connection.execute("SELECT * FROM samples ORDER BY sample").fetchall(),
            connection.execute("SELECT * FROM cell_counts ORDER BY sample, population").fetchall(),
        )


def test_load_schema_values_and_normalization(tmp_path, write_csv):
    database = tmp_path / "test.db"
    assert load_data(write_csv(), database) == (3, 15)
    assert database.is_file()
    with closing(sqlite3.connect(database)) as connection:
        objects = connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
        assert set(objects) == {("samples", "table"), ("cell_counts", "table")}
        columns = {r[1] for r in connection.execute("PRAGMA table_info(samples)")}
        assert columns == {
            "project", "subject", "condition", "age", "sex", "treatment",
            "response", "sample", "sample_type", "time_from_treatment_start",
        }
        assert connection.execute("SELECT COUNT(*) FROM samples").fetchone() == (3,)
        counts = connection.execute("SELECT sample, population, count FROM cell_counts").fetchall()
        assert len(counts) == 15
        assert len({(sample, population) for sample, population, _ in counts}) == 15
        for sample in ("S1", "S2", "S3"):
            assert {p for s, p, _ in counts if s == sample} == POPULATIONS
        assert dict((p, n) for s, p, n in counts if s == "S1") == {
            "b_cell": 10, "cd8_t_cell": 20, "cd4_t_cell": 30, "nk_cell": 20, "monocyte": 20,
        }
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT subject, condition, age, sex, response FROM samples WHERE sample = 'S3'"
        ).fetchone() == ("subject_2", "healthy", 57, "F", None)


@pytest.mark.parametrize("response", ["", "   "])
def test_blank_response_is_null(tmp_path, write_csv, sample_rows, response):
    sample_rows[0]["response"] = response
    database = tmp_path / "test.db"
    load_data(write_csv(), database)
    assert snapshot(database)[0][0][6] is None


@pytest.mark.parametrize("time, expected", [("21", 21), ("-3", -3), ("28.0", 28)])
def test_timepoints_are_not_hardcoded(tmp_path, write_csv, sample_rows, time, expected):
    sample_rows[0]["time_from_treatment_start"] = time
    database = tmp_path / "test.db"
    load_data(write_csv(), database)
    assert snapshot(database)[0][0][-1] == expected


def test_idempotency_and_rebuild_removes_stale_rows(tmp_path, write_csv, sample_rows):
    csv_path, database = write_csv(), tmp_path / "test.db"
    load_data(csv_path, database)
    before = snapshot(database)
    load_data(csv_path, database)
    assert snapshot(database) == before
    load_data(write_csv(rows=sample_rows[:1]), database)
    samples, counts = snapshot(database)
    assert len(samples) == 1
    assert len(counts) == 5


@pytest.mark.parametrize("column", [
    "project", "subject", "condition", "age", "sex", "treatment", "response",
    "sample", "sample_type", "time_from_treatment_start",
    "b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte",
])
def test_missing_required_column(tmp_path, write_csv, sample_rows, column):
    path = write_csv(columns=[c for c in sample_rows[0] if c != column])
    with pytest.raises(ValueError, match=f"Missing required column: {column}"):
        load_data(path, tmp_path / "test.db")
    assert not (tmp_path / "test.db").exists()


@pytest.mark.parametrize("column, value, message", [
    ("sample", "", "missing value for sample"),
    ("subject", " ", "missing value for subject"),
    ("b_cell", "-1", "non-negative"),
    ("b_cell", "abc", "integer"),
    ("b_cell", "1.5", "integer"),
    ("b_cell", "NaN", "integer"),
    ("b_cell", "Infinity", "integer"),
    ("b_cell", str(2**63), "integer"),
    ("b_cell", "", "missing value"),
    ("time_from_treatment_start", "later", "integer"),
    ("time_from_treatment_start", "1.5", "integer"),
    ("time_from_treatment_start", "NaN", "integer"),
    ("age", "-1", "non-negative"),
    ("age", "unknown", "integer"),
    ("sample", " S1", "whitespace"),
])
def test_invalid_values(tmp_path, write_csv, sample_rows, column, value, message):
    sample_rows[0][column] = value
    with pytest.raises(ValueError, match=message):
        load_data(write_csv(), tmp_path / "test.db")


def test_duplicate_sample(tmp_path, write_csv, sample_rows):
    sample_rows[1]["sample"] = "S1"
    with pytest.raises(ValueError, match="duplicate sample identifier: S1"):
        load_data(write_csv(), tmp_path / "test.db")


def test_zero_total(tmp_path, write_csv, sample_rows):
    sample_rows[0].update({p: "0" for p in POPULATIONS})
    with pytest.raises(ValueError, match="zero total"):
        load_data(write_csv(), tmp_path / "test.db")


@pytest.mark.parametrize("mutation, message", [
    (lambda text: "", "empty"),
    (lambda text: text.splitlines()[0] + "\n", "no sample records"),
    (lambda text: text.replace("project,", "sample,", 1), "Duplicate CSV column"),
    (lambda text: text.replace("project,", "extra,project,", 1), "Unexpected columns"),
    (lambda text: text + "too,few\n", "expected 15 fields"),
    (lambda text: text + ",".join(["x"] * 16) + "\n", "expected 15 fields"),
    (lambda text: text + '"unterminated', "Malformed CSV"),
])
def test_malformed_structure(tmp_path, write_csv, mutation, message):
    path = write_csv()
    path.write_text(mutation(path.read_text()))
    with pytest.raises(ValueError, match=message):
        load_data(path, tmp_path / "test.db")


@pytest.mark.parametrize("sql, parameters", [
    ("INSERT INTO cell_counts VALUES (?, ?, ?)", ("S1", "b_cell", 5)),
    ("INSERT INTO cell_counts VALUES (?, ?, ?)", ("missing", "b_cell", 5)),
    ("INSERT INTO cell_counts VALUES (?, ?, ?)", ("S1", "unknown", 5)),
    ("UPDATE cell_counts SET count = ? WHERE sample = 'S1'", (-1,)),
    ("UPDATE cell_counts SET count = ? WHERE sample = 'S1'", (1.5,)),
    ("UPDATE cell_counts SET count = ? WHERE sample = 'S1'", (None,)),
    ("UPDATE samples SET sample = ? WHERE sample = 'S2'", ("S1",)),
    ("UPDATE samples SET sample = ? WHERE sample = 'S2'", (None,)),
])
def test_database_constraints(tmp_path, write_csv, sql, parameters):
    database = tmp_path / "test.db"
    load_data(write_csv(), database)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, parameters)


def test_validation_failure_preserves_existing_database(tmp_path, write_csv, sample_rows):
    database = tmp_path / "test.db"
    load_data(write_csv(), database)
    original = database.read_bytes()
    sample_rows[-1]["monocyte"] = "bad"
    with pytest.raises(ValueError):
        load_data(write_csv(), database)
    assert database.read_bytes() == original
    assert not list(tmp_path.glob(".clinical-trial-*"))


def test_database_failure_preserves_existing_database(tmp_path, write_csv, monkeypatch):
    database, csv_path = tmp_path / "test.db", write_csv()
    load_data(csv_path, database)
    original = database.read_bytes()
    monkeypatch.setattr("src.database.SCHEMA", "INVALID SQL")
    with pytest.raises(sqlite3.OperationalError):
        load_data(csv_path, database)
    assert database.read_bytes() == original
    assert not list(tmp_path.glob(".clinical-trial-*"))


def test_source_cannot_be_output(write_csv):
    path = write_csv()
    before = path.read_bytes()
    with pytest.raises(ValueError, match="different files"):
        load_data(path, path)
    assert path.read_bytes() == before


def test_text_is_preserved_and_values_are_parameterized(tmp_path, write_csv, sample_rows):
    sample_rows[0]["subject"] = "O'Brien'); DROP TABLE samples; --"
    sample_rows[0]["condition"] = "Melanoma"
    sample_rows[0]["b_cell"] = "0"
    database = tmp_path / "test.db"
    load_data(write_csv(columns=list(reversed(sample_rows[0]))), database)
    samples, counts = snapshot(database)
    assert samples[0][1:3] == (sample_rows[0]["subject"], "Melanoma")
    assert ("S1", "b_cell", 0) in counts


def test_cli_without_arguments_from_another_directory(tmp_path, write_csv):
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy(ROOT / "load_data.py", project)
    shutil.copytree(ROOT / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__"))
    write_csv(path=project / "cell-count.csv")
    result = subprocess.run(
        [sys.executable, str(project / "load_data.py")], cwd=tmp_path,
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.splitlines() == [
        "Loaded 3 samples", "Loaded 15 cell-count records", "Created clinical_trial.db",
    ]
    assert (project / "clinical_trial.db").is_file()
    assert not (tmp_path / "clinical_trial.db").exists()
