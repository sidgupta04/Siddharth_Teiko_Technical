from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests

from src.database import load_data
from src.statistics import calculate_statistics, get_responder_data, run_analysis
from src.validation import POPULATIONS


@pytest.fixture
def cohort_rows(sample_rows):
    base = sample_rows[0]
    rows = []
    for i, (response, counts) in enumerate([
        ("yes", [10, 20, 30, 20, 20]),
        ("YES", [20, 15, 25, 30, 10]),
        ("yes", [30, 10, 20, 25, 15]),
        ("no", [5, 25, 35, 15, 20]),
        ("No", [15, 30, 25, 10, 20]),
        ("no", [25, 20, 15, 20, 20]),
    ]):
        rows.append({
            **base, "sample": f"S{i}", "subject": f"subject_{i // 3}",
            "response": response, "condition": "Melanoma", "treatment": "MIRACLIB",
            "sample_type": "pbmc", "time_from_treatment_start": str((i % 3) * 7),
            **dict(zip(POPULATIONS, map(str, counts))),
        })
    return rows


@pytest.fixture
def analysis_database(tmp_path, write_csv, cohort_rows):
    path = tmp_path / "trial.db"
    load_data(write_csv(rows=cohort_rows), path)
    return path


def read_cohort(path):
    with closing(sqlite3.connect(path)) as connection:
        return get_responder_data(connection)


def test_cohort_case_groups_and_all_timepoints(analysis_database):
    rows = read_cohort(analysis_database)
    assert len(rows) == 30
    assert {r["sample"] for r in rows if r["response"] == "yes"} == {"S0", "S1", "S2"}
    assert {r["sample"] for r in rows if r["response"] == "no"} == {"S3", "S4", "S5"}
    assert {r["time_from_treatment_start"] for r in rows} == {0, 7, 14}
    assert len({r["subject"] for r in rows}) == 2


@pytest.mark.parametrize("change", [
    {"condition": "carcinoma"}, {"treatment": "phauximab"},
    {"sample_type": "WB"}, {"response": ""}, {"response": "unknown"},
    {"condition": "melanoma' OR 1=1 --"},
])
def test_each_cohort_exclusion(tmp_path, write_csv, cohort_rows, change):
    cohort_rows.append({**cohort_rows[0], "sample": "excluded", **change})
    path = tmp_path / "trial.db"
    load_data(write_csv(rows=cohort_rows), path)
    assert {r["sample"] for r in read_cohort(path)} == {f"S{i}" for i in range(6)}


def test_statistics_against_scipy_and_expected_medians(analysis_database):
    results = calculate_statistics(read_cohort(analysis_database))
    assert [r["population"] for r in results] == list(POPULATIONS)
    yes = [[10, 20, 30], [20, 15, 10], [30, 25, 20], [20, 30, 25], [20, 10, 15]]
    no = [[5, 15, 25], [25, 30, 20], [35, 25, 15], [15, 10, 20], [20, 20, 20]]
    expected_p = []
    for result, x, y in zip(results, yes, no):
        expected = mannwhitneyu(x, y, alternative="two-sided", method="auto", use_continuity=True)
        assert result["responder_n"] == result["non_responder_n"] == 3
        assert result["responder_median"] == sorted(x)[1]
        assert result["non_responder_median"] == sorted(y)[1]
        assert result["u_statistic"] == expected.statistic
        assert result["p_value"] == pytest.approx(expected.pvalue)
        expected_p.append(expected.pvalue)
    assert [r["adjusted_p_value"] for r in results] == pytest.approx(
        multipletests(expected_p, method="fdr_bh")[1]
    )


def test_relative_frequencies_not_raw_counts(tmp_path, write_csv, cohort_rows):
    for row in cohort_rows:
        multiplier = 10 if row["response"].lower() == "yes" else 1
        row.update({p: str((i + 1) * multiplier) for i, p in enumerate(POPULATIONS)})
    database = tmp_path / "trial.db"
    load_data(write_csv(rows=cohort_rows), database)
    results = run_analysis(database)
    for i, row in enumerate(results):
        assert row["responder_median"] == pytest.approx((i + 1) / 15 * 100)
        assert row["responder_median"] == row["non_responder_median"]
        assert row["p_value"] == row["adjusted_p_value"] == 1.0
        assert row["significant"] == 0


def test_known_bh_example_and_strict_significance(analysis_database, monkeypatch):
    # Unsorted p-values check mapping back to populations; raw 0.04 loses significance.
    raw = iter([0.2, 0.01, 0.04, 0.001, 0.06])
    monkeypatch.setattr("src.statistics.mannwhitneyu", lambda *a, **k: SimpleNamespace(statistic=1, pvalue=next(raw)))
    results = calculate_statistics(read_cohort(analysis_database))
    assert [r["adjusted_p_value"] for r in results] == pytest.approx([0.2, 0.025, 0.04 * 5 / 3, 0.005, 0.075])
    assert [r["significant"] for r in results] == [0, 1, 0, 1, 0]


def test_exact_significance_boundary(analysis_database, monkeypatch):
    adjusted = [0.05, 0.049, 0.051, 0.0, 1.0]
    monkeypatch.setattr("src.statistics.multipletests", lambda *a, **k: (None, adjusted))
    results = calculate_statistics(read_cohort(analysis_database))
    assert [r["significant"] for r in results] == [0, 1, 0, 1, 0]


def test_persistence_idempotency_and_source_unchanged(analysis_database):
    with closing(sqlite3.connect(analysis_database)) as c:
        before = {table: c.execute(f"SELECT * FROM {table}").fetchall()
                  for table in ("samples", "cell_counts", "cell_frequencies")}
    expected = run_analysis(analysis_database)
    assert run_analysis(analysis_database) == expected
    with closing(sqlite3.connect(analysis_database)) as c:
        c.row_factory = sqlite3.Row
        saved = {row["population"]: dict(row) for row in c.execute("SELECT * FROM population_statistics")}
        assert saved == {r["population"]: r for r in expected}
        assert len(saved) == 5
        c.row_factory = None
        for table, rows in before.items():
            assert c.execute(f"SELECT * FROM {table}").fetchall() == rows


@pytest.mark.parametrize("response", ["yes", "no", "unknown"])
def test_empty_group_fails_without_results(tmp_path, write_csv, cohort_rows, response):
    for row in cohort_rows:
        row["response"] = response
    database = tmp_path / "trial.db"
    load_data(write_csv(rows=cohort_rows), database)
    with pytest.raises(ValueError, match="Both response groups"):
        run_analysis(database)
    with closing(sqlite3.connect(database)) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE name='population_statistics'").fetchall() == []


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -1, 101])
def test_invalid_frequency_rejected(analysis_database, value):
    rows = [dict(r) for r in read_cohort(analysis_database)]
    rows[0]["percentage"] = value
    with pytest.raises(ValueError, match="Invalid percentage"):
        calculate_statistics(rows)


def test_missing_or_duplicate_population_rejected(analysis_database):
    rows = read_cohort(analysis_database)
    with pytest.raises(ValueError, match="Incomplete"):
        calculate_statistics(rows[1:])
    with pytest.raises(ValueError, match="Duplicate"):
        calculate_statistics(rows + [rows[0]])


def test_failed_analysis_preserves_previous_results(analysis_database):
    run_analysis(analysis_database)
    with closing(sqlite3.connect(analysis_database)) as c:
        before = c.execute("SELECT * FROM population_statistics").fetchall()
        c.execute("UPDATE cell_counts SET count = 0 WHERE sample = 'S0'")
        c.commit()
    with pytest.raises(ValueError, match="Invalid percentage"):
        run_analysis(analysis_database)
    with closing(sqlite3.connect(analysis_database)) as c:
        assert c.execute("SELECT * FROM population_statistics").fetchall() == before


def test_persistence_failure_rolls_back(analysis_database):
    run_analysis(analysis_database)
    with closing(sqlite3.connect(analysis_database)) as c:
        before = c.execute("SELECT * FROM population_statistics").fetchall()
        c.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON population_statistics BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        c.commit()
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        run_analysis(analysis_database)
    with closing(sqlite3.connect(analysis_database)) as c:
        assert c.execute("SELECT * FROM population_statistics").fetchall() == before


def test_missing_database_not_created(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError, match="load_data.py"):
        run_analysis(path)
    assert not path.exists()


def test_cli_no_arguments_and_repository_relative_paths(tmp_path, write_csv, cohort_rows):
    root = Path(__file__).resolve().parents[1]
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy(root / "run_analysis.py", project)
    shutil.copytree(root / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__"))
    database = project / "clinical_trial.db"
    load_data(write_csv(rows=cohort_rows), database)
    result = subprocess.run([sys.executable, str(project / "run_analysis.py")], cwd=tmp_path,
                            capture_output=True, text=True, check=True)
    assert "Analyzed 5 populations" in result.stdout
    assert "repeated samples" in result.stdout
    with closing(sqlite3.connect(database)) as c:
        assert c.execute("SELECT COUNT(*) FROM population_statistics").fetchone() == (5,)
