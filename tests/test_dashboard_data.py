from contextlib import closing
import sqlite3

import pandas as pd
import pytest

from src.dashboard_data import filter_frequency_data, get_statistics, load_dashboard_data
from src.database import load_data
from src.deployment import bootstrap_database, is_streamlit_cloud
from src.statistics import run_analysis


@pytest.fixture
def dashboard_database(tmp_path, write_csv, pipeline_rows):
    path = tmp_path / "dashboard.db"
    load_data(write_csv(rows=pipeline_rows), path)
    run_analysis(path)
    return path


def test_dashboard_assembly_reuses_required_results(dashboard_database):
    before = dashboard_database.read_bytes()
    data = load_dashboard_data(dashboard_database)
    assert data["total_samples"] == 7
    assert len(data["overview"]) == 35
    assert set(data["overview"]["sample"]) == {f"S{i}" for i in range(1, 8)}
    assert len(data["responders"]) == 20
    assert set(data["responders"]["sample"]) == {"S1", "S2", "S5", "S7"}
    assert data["statistics"]["responder_n"].tolist() == [3] * 5
    assert data["statistics"]["non_responder_n"].tolist() == [1] * 5
    assert data["project_counts"].to_dict("records") == [
        {"project": "p1", "sample_count": 2}, {"project": "p2", "sample_count": 1},
    ]
    assert data["response_counts"].to_dict("records") == [
        {"response": "no", "subject_count": 1}, {"response": "yes", "subject_count": 1},
    ]
    assert data["sex_counts"]["subject_count"].tolist() == [1, 1]
    assert data["bcell_average"] == 37.5
    assert dashboard_database.read_bytes() == before


@pytest.mark.parametrize("filters, samples", [
    ({}, {"S1", "S2", "S3", "S4", "S5", "S6", "S7"}),
    ({"sample_search": "s1"}, {"S1"}),
    ({"sample_search": ".*"}, set()),
    ({"condition": "CARCINOMA"}, {"S6"}),
    ({"treatment": "OTHER"}, {"S3"}),
    ({"timepoint": 7}, {"S5"}),
    ({"condition": "melanoma", "treatment": "miraclib", "timepoint": 0}, {"S1", "S2", "S4", "S7"}),
    ({"sample_search": "missing"}, set()),
])
def test_overview_filters(dashboard_database, filters, samples):
    data = load_dashboard_data(dashboard_database)
    before = data["overview"].copy(deep=True)
    filtered = filter_frequency_data(data["overview"], **filters)
    assert set(filtered["sample"]) == samples
    assert len(filtered) == len(samples) * 5
    pd.testing.assert_frame_equal(data["overview"], before)
    assert data["statistics"]["responder_n"].tolist() == [3] * 5


def test_reads_persisted_statistics_without_recalculation(dashboard_database, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Dashboard must not calculate statistics")
    monkeypatch.setattr("src.statistics.calculate_statistics", fail)
    with closing(sqlite3.connect(dashboard_database)) as connection:
        connection.execute("UPDATE population_statistics SET p_value=0.777, adjusted_p_value=0.888, significant=0")
        connection.commit()
        stats = get_statistics(connection)
    assert stats["p_value"].tolist() == [0.777] * 5
    assert load_dashboard_data(dashboard_database)["statistics"]["adjusted_p_value"].tolist() == [0.888] * 5


def test_missing_database_does_not_create_file(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError, match="make pipeline"):
        load_dashboard_data(path)
    assert not path.exists()


def test_loader_only_database_is_incomplete(tmp_path, write_csv):
    path = tmp_path / "incomplete.db"
    load_data(write_csv(), path)
    with pytest.raises(ValueError, match="make pipeline"):
        load_dashboard_data(path)


def test_partial_statistics_are_rejected(dashboard_database):
    with closing(sqlite3.connect(dashboard_database)) as connection:
        connection.execute("DELETE FROM population_statistics WHERE population='b_cell'")
        connection.commit()
    with pytest.raises(ValueError, match="Incomplete statistics"):
        load_dashboard_data(dashboard_database)


def test_corrupt_database_is_explained(tmp_path):
    path = tmp_path / "bad.db"
    path.write_text("not sqlite")
    with pytest.raises(ValueError, match="make pipeline"):
        load_dashboard_data(path)


def test_local_environment_does_not_enable_cloud_bootstrap():
    assert is_streamlit_cloud({}) is False
    assert is_streamlit_cloud({"STREAMLIT_CLOUD": "0", "USER": "developer"}) is False


@pytest.mark.parametrize("key", ["STREAMLIT_CLOUD", "IS_STREAMLIT_CLOUD", "STREAMLIT_SHARING_MODE"])
def test_explicit_cloud_markers_enable_bootstrap(key):
    assert is_streamlit_cloud({key: "true"}) is True


def test_streamlit_runtime_cloud_marker_enables_bootstrap():
    assert is_streamlit_cloud({"STREAMLIT_RUNTIME_ENV": "cloud"}) is True
    assert is_streamlit_cloud({"STREAMLIT_RUNTIME_ENV": "local"}) is False


def test_known_cloud_runtime_marker_enables_bootstrap():
    assert is_streamlit_cloud({"USER": "appuser"}) is True


def test_cloud_bootstrap_builds_complete_database(tmp_path, write_csv, pipeline_rows):
    database = tmp_path / "clinical_trial.db"
    csv_path = write_csv(rows=pipeline_rows)
    assert bootstrap_database(database, csv_path) is True
    assert database.exists()
    data = load_dashboard_data(database)
    assert data["total_samples"] == 7
    assert len(data["statistics"]) == 5
    assert bootstrap_database(database, csv_path) is False


def test_cloud_bootstrap_does_not_replace_existing_database(tmp_path, write_csv, pipeline_rows):
    database = tmp_path / "clinical_trial.db"
    csv_path = write_csv(rows=pipeline_rows)
    database.write_bytes(b"existing")
    before = database.read_bytes()
    assert bootstrap_database(database, csv_path) is False
    assert database.read_bytes() == before
