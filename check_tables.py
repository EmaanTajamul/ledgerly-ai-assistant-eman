from main import get_connection

connection = get_connection()

row = connection.execute(
    "SELECT sql FROM sqlite_master "
    "WHERE type='table' AND name='approval_requests'"
).fetchone()

print(row["sql"] if row else "Table not found")

connection.close()