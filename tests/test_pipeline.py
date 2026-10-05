from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from src.dashboard_data import load_dashboard_data


def test_make_pipeline_from_clean_synthetic_project(tmp_path, write_csv, pipeline_rows):
    root = Path(__file__).resolve().parents[1]
    project = tmp_path / "project"
    project.mkdir()
    for name in ("Makefile", "load_data.py", "run_analysis.py"):
        shutil.copy(root / name, project)
    shutil.copytree(root / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__"))
    source = write_csv(rows=pipeline_rows, path=project / "cell-count.csv")
    source_before = source.read_bytes()
    database = project / "clinical_trial.db"
    assert not database.exists()
    command = ["make", "pipeline", f"PYTHON={sys.executable}"]
    completed = subprocess.run(command, cwd=project, capture_output=True, text=True, check=True)
    assert "Loaded 7 samples" in completed.stdout
    assert "Analyzed 5 populations" in completed.stdout
    with closing(sqlite3.connect(database)) as connection:
        before = list(connection.iterdump())
        assert connection.execute("SELECT COUNT(*) FROM samples").fetchone() == (7,)
        assert connection.execute("SELECT COUNT(*) FROM cell_counts").fetchone() == (35,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT total_count, count, percentage FROM cell_frequencies WHERE sample='S1' AND population='b_cell'").fetchone() == (100, 10, 10.0)
        for total, in connection.execute("SELECT SUM(percentage) FROM cell_frequencies GROUP BY sample"):
            assert total == pytest.approx(100.0)
        statistics = connection.execute("SELECT responder_n, non_responder_n, p_value, adjusted_p_value, significant FROM population_statistics").fetchall()
        assert len(statistics) == 5
        for yes, no, p, adjusted, significant in statistics:
            assert (yes, no) == (3, 1)
            assert 0 <= p <= adjusted <= 1
            assert significant == int(adjusted < 0.05)
    data = load_dashboard_data(database)
    assert data["project_counts"].to_dict("records") == [{"project": "p1", "sample_count": 2}, {"project": "p2", "sample_count": 1}]
    assert data["response_counts"]["subject_count"].tolist() == [1, 1]
    assert data["sex_counts"]["subject_count"].tolist() == [1, 1]
    assert data["bcell_average"] == 37.5
    subprocess.run(command, cwd=project, capture_output=True, text=True, check=True)
    with closing(sqlite3.connect(database)) as connection:
        assert list(connection.iterdump()) == before
    assert source.read_bytes() == source_before
