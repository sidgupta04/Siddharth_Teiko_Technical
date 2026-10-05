from contextlib import closing
import sqlite3

import pytest

from src.database import load_data
from src.queries import (
    format_bcell_average,
    get_bcell_average,
    get_project_counts,
    get_response_subject_counts,
    get_sex_subject_counts,
)


@pytest.fixture
def subset_rows(sample_rows):
    base = sample_rows[0]
    # Two samples from the same subject at baseline expose COUNT(*) mistakes.
    changes = [
        {"sample": "A", "subject": "a", "project": "p1", "b_cell": "10"},
        {"sample": "B", "subject": "a", "project": "p1", "b_cell": "20"},
        {"sample": "C", "subject": "b", "project": "p1", "sex": "F", "response": "no"},
        {"sample": "D", "subject": "c", "project": "p2", "b_cell": "30"},
        {"sample": "E", "subject": "d", "treatment": "other", "b_cell": "40"},
        {"sample": "F", "subject": "e", "sample_type": "WB", "b_cell": "50"},
        {"sample": "G", "subject": "f", "condition": "carcinoma", "b_cell": "999"},
        {"sample": "H", "subject": "g", "time_from_treatment_start": "7", "b_cell": "999"},
    ]
    return [{**base, **change} for change in changes]


@pytest.fixture
def subset_database(tmp_path, write_csv, subset_rows):
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=subset_rows), path)
    return path


def test_samples_by_project(subset_database):
    with closing(sqlite3.connect(subset_database)) as c:
        assert [dict(r) for r in get_project_counts(c)] == [
            {"project": "p1", "sample_count": 3},
            {"project": "p2", "sample_count": 1},
        ]


def test_distinct_subjects_by_response(subset_database):
    with closing(sqlite3.connect(subset_database)) as c:
        assert [dict(r) for r in get_response_subject_counts(c)] == [
            {"response": "no", "subject_count": 1},
            {"response": "yes", "subject_count": 2},
        ]


def test_distinct_subjects_by_sex(subset_database):
    with closing(sqlite3.connect(subset_database)) as c:
        assert [dict(r) for r in get_sex_subject_counts(c)] == [
            {"sex": "F", "subject_count": 1},
            {"sex": "M", "subject_count": 2},
        ]


@pytest.mark.parametrize("change", [
    {"condition": "healthy"}, {"sample_type": "WB"},
    {"treatment": "other"}, {"time_from_treatment_start": "14"},
])
def test_each_base_cohort_filter(tmp_path, write_csv, sample_rows, change):
    row = {**sample_rows[0], **change}
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=[row]), path)
    with closing(sqlite3.connect(path)) as c:
        assert get_project_counts(c) == []
        assert get_response_subject_counts(c) == []
        assert get_sex_subject_counts(c) == []


def test_bcell_mean_uses_all_sample_and_treatment_types(subset_database):
    with closing(sqlite3.connect(subset_database)) as c:
        # Both samples from subject a count, plus other treatment and WB samples.
        assert get_bcell_average(c) == pytest.approx((10 + 20 + 30 + 40 + 50) / 5)


@pytest.mark.parametrize("change", [
    {"treatment": "phauximab"}, {"sample_type": "WB"},
    {"treatment": "other", "sample_type": "tissue"},
])
def test_bcell_broader_cohort_inclusions(tmp_path, write_csv, sample_rows, change):
    first = {**sample_rows[0], "b_cell": "10"}
    second = {**first, **change, "sample": "extra", "b_cell": "50"}
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=[first, second]), path)
    with closing(sqlite3.connect(path)) as c:
        assert get_bcell_average(c) == 30.0


@pytest.mark.parametrize("change", [
    {"condition": "carcinoma"}, {"sex": "F"}, {"response": "no"},
    {"response": ""}, {"response": "unknown"}, {"time_from_treatment_start": "7"},
])
def test_bcell_each_required_filter(tmp_path, write_csv, sample_rows, change):
    first = {**sample_rows[0], "b_cell": "10"}
    excluded = {**first, **change, "sample": "excluded", "b_cell": "999"}
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=[first, excluded]), path)
    with closing(sqlite3.connect(path)) as c:
        assert get_bcell_average(c) == 10.0


def test_case_insensitive_filters_and_grouping(tmp_path, write_csv, sample_rows):
    first = sample_rows[0]
    second = {**first, "sample": "extra", "condition": "Melanoma",
              "sample_type": "pbmc", "treatment": "MIRACLIB", "response": "YES", "sex": "m"}
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=[first, second]), path)
    with closing(sqlite3.connect(path)) as c:
        assert get_project_counts(c)[0]["sample_count"] == 2
        assert [dict(r) for r in get_response_subject_counts(c)] == [{"response": "yes", "subject_count": 1}]
        assert [dict(r) for r in get_sex_subject_counts(c)] == [{"sex": "M", "subject_count": 1}]
        assert get_bcell_average(c) == 10.0
        assert c.execute("SELECT response, sex FROM samples WHERE sample = 'extra'").fetchone() == ("YES", "m")


def test_base_cohort_retains_null_and_other_responses(tmp_path, write_csv, sample_rows):
    rows = [{**sample_rows[0], "response": ""},
            {**sample_rows[0], "sample": "extra", "subject": "other", "response": "unknown"}]
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=rows), path)
    with closing(sqlite3.connect(path)) as c:
        assert get_project_counts(c)[0]["sample_count"] == 2
        assert get_response_subject_counts(c) == []
        assert get_sex_subject_counts(c)[0]["subject_count"] == 2
        assert get_bcell_average(c) is None
        assert format_bcell_average(get_bcell_average(c)) == "N/A"


def test_response_summary_excludes_null_and_other_in_mixed_cohort(tmp_path, write_csv, sample_rows):
    rows = [
        {**sample_rows[0], "sample": str(i), "subject": subject, "response": response}
        for i, (subject, response) in enumerate([
            ("a", "yes"), ("a", "YES"), ("b", "No"),
            ("c", ""), ("d", "unknown"),
        ])
    ]
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=rows), path)
    with closing(sqlite3.connect(path)) as c:
        assert [dict(r) for r in get_response_subject_counts(c)] == [
            {"response": "no", "subject_count": 1},
            {"response": "yes", "subject_count": 1},
        ]
        assert get_project_counts(c)[0]["sample_count"] == 5
        assert get_sex_subject_counts(c)[0]["subject_count"] == 4


@pytest.mark.parametrize("value, expected", [
    (0, "0.00"), (10, "10.00"), (12.3, "12.30"),
    (10 / 3, "3.33"), (12.346, "12.35"), (None, "N/A"),
])
def test_two_decimal_formatting(value, expected):
    assert format_bcell_average(value) == expected


def test_zero_bcell_mean_is_not_missing(tmp_path, write_csv, sample_rows):
    path = tmp_path / "subset.db"
    load_data(write_csv(rows=[{**sample_rows[0], "b_cell": "0"}]), path)
    with closing(sqlite3.connect(path)) as c:
        assert get_bcell_average(c) == 0.0
        assert format_bcell_average(get_bcell_average(c)) == "0.00"


def test_readonly_helpers_preserve_database_and_connection(subset_database):
    with closing(sqlite3.connect(subset_database.as_uri() + "?mode=ro", uri=True)) as c:
        before = list(c.iterdump())
        for factory in (None, sqlite3.Row):
            c.row_factory = factory
            for query in (get_project_counts, get_response_subject_counts, get_sex_subject_counts, get_bcell_average):
                query(c)
                assert c.row_factory is factory
                assert not c.in_transaction
        c.row_factory = None
        assert list(c.iterdump()) == before
