from collections import defaultdict
from contextlib import closing
import sqlite3

import pytest

from src.database import load_data
from src.frequencies import get_frequency_data


@pytest.fixture
def frequency_database(tmp_path, write_csv):
    database = tmp_path / "frequencies.db"
    load_data(write_csv(), database)
    return database


def test_view_schema_and_exact_example(frequency_database):
    with closing(sqlite3.connect(frequency_database)) as connection:
        assert connection.execute(
            "SELECT type FROM sqlite_master WHERE name = 'cell_frequencies'"
        ).fetchone() == ("view",)
        cursor = connection.execute("SELECT * FROM cell_frequencies WHERE sample = 'S1'")
        assert [column[0] for column in cursor.description] == [
            "sample", "total_count", "population", "count", "percentage",
        ]
        rows = cursor.fetchall()
    assert sorted(rows) == sorted([
        ("S1", 100, "b_cell", 10, 10.0),
        ("S1", 100, "cd8_t_cell", 20, 20.0),
        ("S1", 100, "cd4_t_cell", 30, 30.0),
        ("S1", 100, "nk_cell", 20, 20.0),
        ("S1", 100, "monocyte", 20, 20.0),
    ])
    assert all(isinstance(row[1], int) and isinstance(row[4], float) for row in rows)


def test_each_sample_has_five_rows_and_percentages_sum_to_100(
    tmp_path, write_csv, sample_rows,
):
    # Same subject, different totals: normalization must be per sample.
    sample_rows[1].update(b_cell="1", cd8_t_cell="1", cd4_t_cell="1", nk_cell="0", monocyte="0")
    sample_rows[2].update(b_cell="7", cd8_t_cell="11", cd4_t_cell="13", nk_cell="17", monocyte="19")
    database = tmp_path / "test.db"
    load_data(write_csv(), database)
    with closing(sqlite3.connect(database)) as connection:
        rows = get_frequency_data(connection)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["sample"]].append(row)
    assert set(grouped) == {"S1", "S2", "S3"}  # Includes NULL response and WB.
    assert len(rows) == 15
    for sample, expected_total in {"S1": 100, "S2": 3, "S3": 67}.items():
        values = grouped[sample]
        assert len(values) == 5
        assert len({row["population"] for row in values}) == 5
        assert {row["total_count"] for row in values} == {expected_total}
        assert sum(row["percentage"] for row in values) == pytest.approx(100.0)
        for row in values:
            assert row["percentage"] == pytest.approx(row["count"] / expected_total * 100)
    b_cell = next(row for row in grouped["S2"] if row["population"] == "b_cell")
    assert b_cell["percentage"] == pytest.approx(100 / 3, abs=1e-12)
    assert b_cell["percentage"] != 33.33


def test_zero_population_with_positive_total(tmp_path, write_csv, sample_rows):
    sample_rows[0].update(b_cell="0", cd8_t_cell="0", cd4_t_cell="0", nk_cell="0", monocyte="5")
    database = tmp_path / "test.db"
    load_data(write_csv(), database)
    with closing(sqlite3.connect(database)) as connection:
        values = {
            row["population"]: row["percentage"]
            for row in get_frequency_data(connection) if row["sample"] == "S1"
        }
    assert values == {"b_cell": 0.0, "cd8_t_cell": 0.0, "cd4_t_cell": 0.0, "nk_cell": 0.0, "monocyte": 100.0}


def test_zero_total_is_rejected_before_database_creation(tmp_path, write_csv, sample_rows):
    sample_rows[0].update(b_cell="0", cd8_t_cell="0", cd4_t_cell="0", nk_cell="0", monocyte="0")
    database = tmp_path / "test.db"
    with pytest.raises(ValueError, match="zero total cell count"):
        load_data(write_csv(), database)
    assert not database.exists()


def test_view_reflects_updated_counts(frequency_database):
    with closing(sqlite3.connect(frequency_database)) as connection:
        connection.execute(
            "UPDATE cell_counts SET count = ? WHERE sample = ? AND population = ?",
            (110, "S1", "b_cell"),
        )
        rows = [row for row in get_frequency_data(connection) if row["sample"] == "S1"]
        assert {row["total_count"] for row in rows} == {200}
        assert next(row["percentage"] for row in rows if row["population"] == "b_cell") == 55.0
        assert sum(row["percentage"] for row in rows) == pytest.approx(100.0)


def test_zero_total_after_direct_sql_update_has_null_percentages(frequency_database):
    # The loader rejects zero totals; guard undefined frequencies if SQL bypasses it.
    with closing(sqlite3.connect(frequency_database)) as connection:
        connection.execute("UPDATE cell_counts SET count = 0 WHERE sample = 'S1'")
        rows = [row for row in get_frequency_data(connection) if row["sample"] == "S1"]
        assert len(rows) == 5
        assert all(row["total_count"] == 0 and row["percentage"] is None for row in rows)


@pytest.mark.parametrize("row_factory", [None, sqlite3.Row])
def test_helper_named_fields_order_and_connection_ownership(frequency_database, row_factory):
    with closing(sqlite3.connect(frequency_database)) as connection:
        connection.row_factory = row_factory
        rows = get_frequency_data(connection)
        assert rows[0].keys() == ["sample", "total_count", "population", "count", "percentage"]
        keys = [(row["sample"], row["population"]) for row in rows]
        assert keys == sorted(keys)
        assert connection.row_factory is row_factory
        assert not connection.in_transaction
        connection.execute("UPDATE cell_counts SET count = 40 WHERE sample = 'S1' AND population = 'b_cell'")
        get_frequency_data(connection)
        assert connection.in_transaction  # Reading must not commit the caller's work.
        connection.rollback()
        assert get_frequency_data(connection)[0]["count"] == 10


def test_rebuild_preserves_frequency_results(frequency_database, write_csv):
    with closing(sqlite3.connect(frequency_database)) as connection:
        before = [dict(row) for row in get_frequency_data(connection)]
    load_data(write_csv(), frequency_database)
    with closing(sqlite3.connect(frequency_database)) as connection:
        assert [dict(row) for row in get_frequency_data(connection)] == before


def test_empty_counts_return_no_frequencies(frequency_database):
    with closing(sqlite3.connect(frequency_database)) as connection:
        connection.execute("DELETE FROM cell_counts")
        assert get_frequency_data(connection) == []
