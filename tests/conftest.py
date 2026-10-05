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
