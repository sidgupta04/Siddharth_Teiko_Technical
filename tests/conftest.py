import csv

import pytest


@pytest.fixture
def sample_rows():
    base = dict(
        project="prj_test", subject="subject_1", condition="melanoma", age="57",
        sex="M", treatment="miraclib", response="yes", sample="S1",
        sample_type="PBMC", time_from_treatment_start="0", b_cell="10",
        cd8_t_cell="20", cd4_t_cell="30", nk_cell="20", monocyte="20",
    )
    return [
        base,
        {**base, "sample": "S2", "time_from_treatment_start": "21"},
        {**base, "sample": "S3", "subject": "subject_2", "condition": "healthy",
         "treatment": "none", "response": "", "sex": "F", "sample_type": "WB"},
    ]


@pytest.fixture
def write_csv(tmp_path, sample_rows):
    def write(rows=None, columns=None, path=None):
        rows = sample_rows if rows is None else rows
        columns = list(sample_rows[0]) if columns is None else columns
        path = tmp_path / "cell-count.csv" if path is None else path
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path
    return write


@pytest.fixture
def pipeline_rows(sample_rows):
    """Small end-to-end cohort with exclusions and repeated baseline subjects."""
    base = {**sample_rows[0], "project": "p1"}
    changes = [
        {"sample": "S1", "b_cell": "10"},
        {"sample": "S2", "subject": "subject_2", "response": "no", "sex": "F", "b_cell": "20"},
        {"sample": "S3", "subject": "subject_3", "treatment": "other", "b_cell": "30"},
        {"sample": "S4", "subject": "subject_4", "sample_type": "WB", "b_cell": "40"},
        {"sample": "S5", "time_from_treatment_start": "7", "b_cell": "50"},
        {"sample": "S6", "subject": "subject_6", "condition": "carcinoma", "b_cell": "60"},
        {"sample": "S7", "project": "p2", "b_cell": "70"},
    ]
    return [{**base, **change} for change in changes]
