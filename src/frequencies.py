"""Read per-sample frequencies calculated by the SQLite view."""

import sqlite3


def get_frequency_data(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all samples' five frequency fields, ordered by sample/population.

    Rows support column-name access. Percentages retain floating-point precision
    without display rounding. The caller owns the connection; its row factory
    and transaction state are left unchanged. Run the loader to create the view.
    """
    cursor = connection.cursor()
    try:
        cursor.row_factory = sqlite3.Row
        return cursor.execute(
            "SELECT sample, total_count, population, count, percentage "
            "FROM cell_frequencies ORDER BY sample, population"
        ).fetchall()
    finally:
        cursor.close()
