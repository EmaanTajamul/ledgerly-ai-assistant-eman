
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "ecommerce_generated.db"

with sqlite3.connect(DB_PATH) as connection:
    print("--- INVENTORY SUMMARY ---")

    rows = connection.execute("""
        SELECT
            COUNT(*) AS total_variants,
            SUM(CASE WHEN available_units = 0 THEN 1 ELSE 0 END)
                AS out_of_stock,
            SUM(CASE
                WHEN available_units <= reorder_threshold THEN 1
                ELSE 0
            END) AS at_or_below_threshold
        FROM inventory
    """).fetchall()

    print(rows[0])

    print("\n--- INVENTORY SAMPLE ---")

    rows = connection.execute("""
        SELECT
            variant_id,
            available_units,
            reorder_threshold,
            updated_at
        FROM inventory
        ORDER BY available_units ASC
        LIMIT 10
    """).fetchall()

    for row in rows:
        print(row)
