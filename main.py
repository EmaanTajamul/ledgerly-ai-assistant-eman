
import sqlite3
import requests
import json

from pathlib import Path
from datetime import date


# 1. Find the existing database
DB_PATH = Path(__file__).parent / "ecommerce_generated.db"


# 2. Connect to the database
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def save_tool_run(
    request_id,
    tool,
    arguments,
    duration_ms,
    status,
    result,
    error_message=None,
):
    """Save one tool execution to tool_runs."""
    import json
    from datetime import datetime

    connection = get_connection()

    try:
        now = datetime.now().isoformat(timespec="seconds")

        connection.execute(
            """
            INSERT INTO tool_runs (
                request_id, tool, arguments, duration_ms,
                status, result, error_message,
                started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                tool,
                json.dumps(arguments, default=str),
                int(duration_ms),
                status,
                json.dumps(result, default=str),
                error_message,
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def save_approval_request(action, payload, requester="AI Assistant"):
    # Keep your existing function body here, unchanged.

    """Save a proposal for human review and return its request ID."""
    import json
    from datetime import datetime

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO approval_requests (
                action,
                payload,
                status,
                requester,
                requested_at
            )
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (
                action,
                json.dumps(payload, default=str),
                requester,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        connection.commit()

        return {
            "request_id": cursor.lastrowid,
            "status": "pending",
            "message": "Proposal saved for human approval.",
        }

    finally:
        connection.close()



# 3. Validate dates
def valid_date(value):
    """Check whether a date uses YYYY-MM-DD format."""
    if not isinstance(value, str):
        return False

    try:
        parsed_date = date.fromisoformat(value)
        return parsed_date.isoformat() == value
    except ValueError:
        return False


# 4. Create the audit log table
def create_audit_logs_table():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                arguments TEXT,
                result TEXT,
                duration_ms REAL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
    finally:
        connection.close()


# 5. Save tool execution records
def save_audit_log(
    request_id,
    tool_name,
    arguments,
    result,
    duration_ms,
    status
):
    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO audit_logs (
                request_id,
                tool_name,
                arguments,
                result,
                duration_ms,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            tool_name,
            json.dumps(arguments, default=str),
            json.dumps(result, default=str),
            duration_ms,
            status
        ))
        connection.commit()
    finally:
        connection.close()

#TOOL 1: Search products

def search_products(query="", category="", limit=10):
    """Search products by name or category."""

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        return {"error": "Limit must be an integer between 1 and 100"}

    if not isinstance(query, str) or not isinstance(category, str):
        return {"error": "Query and category must be strings"}

    with get_connection() as connection:
        sql = """
            SELECT
                p.product_id,
                p.title,
                p.category,
                p.status
            FROM products AS p
            WHERE 1 = 1
        """

        params = []

        if query.strip():
            sql += " AND p.title LIKE ?"
            params.append(f"%{query.strip()}%")

        if category.strip():
            sql += " AND p.category = ?"
            params.append(category.strip())

        sql += " ORDER BY p.title LIMIT ?"
        params.append(limit)

        rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]



    #2 TOOL: Get product details
def get_product_details(product_id):
    """Get details of one product using its ID."""

    with get_connection() as connection:
        sql = """
            SELECT *
            FROM products
            WHERE product_id = ?
        """

        row = connection.execute(
            sql, (product_id,)
        ).fetchone()

        if row is None:
            return {"error": "Product not found"}

        return dict(row)


    #htird tool Get inventory for a product variant
def get_inventory(variant_id):
    """Get available stock and reorder threshold for a variant."""

    with get_connection() as connection:
        sql = """
            SELECT
                v.variant_id,
                v.product_id,
                v.sku,
                v.size,
                v.color,
                i.available_units,
                i.reorder_threshold,
                i.updated_at
            FROM variants AS v
            JOIN inventory AS i
                ON v.variant_id = i.variant_id
            WHERE v.variant_id = ?
        """

        row = connection.execute(sql, (variant_id,)).fetchone()

        if row is None:
            return {"error": "Variant or inventory not found"}

        return dict(row)

    # Tool 4: Get an order and its items
def get_order(order_id):
    """Get order details and all items belonging to that order."""

    with get_connection() as connection:

        # Get the main order information
        order_sql = """
            SELECT *
            FROM orders
            WHERE order_id = ?
        """

        order_row = connection.execute(
            order_sql, (order_id,)
        ).fetchone()

        if order_row is None:
            return {"error": "Order not found"}

        order = dict(order_row)

        # Get all items in this order
        items_sql = """
            SELECT
                oi.order_item_id,
                oi.variant_id,
                p.title AS product_title,
                v.sku,
                oi.quantity,
                oi.unit_price,
                oi.discount
            FROM order_items AS oi
            JOIN variants AS v
                ON oi.variant_id = v.variant_id
            JOIN products AS p
                ON v.product_id = p.product_id
            WHERE oi.order_id = ?
        """

        item_rows = connection.execute(
            items_sql, (order_id,)
        ).fetchall()

        order["items"] = [dict(row) for row in item_rows]

        return order

    
# Tool 5: Get customer summary
def get_customer_summary(customer_id):
    """Return customer details and a summary of their orders."""

    with get_connection() as connection:

        # Get customer information
        customer_sql = """
            SELECT
                customer_id,
                full_name,
                email,
                country,
                created_at
            FROM customers
            WHERE customer_id = ?
        """

        customer_row = connection.execute(
            customer_sql, (customer_id,)
        ).fetchone()

        if customer_row is None:
            return {"error": "Customer not found"}

        customer = dict(customer_row)

        # Calculate purchase summary
        summary_sql = """
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(total_amount), 0) AS total_spent,
                COALESCE(AVG(total_amount), 0) AS average_order_value
            FROM orders
            WHERE customer_id = ?
              AND status != 'cancelled'
        """

        summary_row = connection.execute(
            summary_sql, (customer_id,)
        ).fetchone()

        customer["purchase_summary"] = dict(summary_row)

        return customer

    #TOOL 6

def get_sales_summary(start_date, end_date):
    """Calculate order, revenue, AOV, and refund totals for a date range."""

    if not valid_date(start_date) or not valid_date(end_date):
        return {"error": "Dates must use YYYY-MM-DD format"}

    if start_date > end_date:
        return {"error": "Start date cannot be after end date"}

    with get_connection() as connection:
        sales_sql = """
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(total_amount), 0) AS total_revenue,
                COALESCE(AVG(total_amount), 0) AS average_order_value
            FROM orders
            WHERE order_date BETWEEN ? AND ?
              AND status != 'cancelled'
        """

        sales_row = connection.execute(
            sales_sql, (start_date, end_date)
        ).fetchone()

        refunds_sql = """
            SELECT
                COUNT(*) AS total_refunds,
                COALESCE(SUM(amount), 0) AS total_refund_amount
            FROM refunds
            WHERE refund_date BETWEEN ? AND ?
              AND status = 'completed'
        """

        refunds_row = connection.execute(
            refunds_sql, (start_date, end_date)
        ).fetchone()

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_orders": sales_row["total_orders"],
            "total_revenue": round(sales_row["total_revenue"], 2),
            "average_order_value": round(
                sales_row["average_order_value"], 2
            ),
            "total_refunds": refunds_row["total_refunds"],
            "total_refund_amount": round(
                refunds_row["total_refund_amount"], 2
            )
        }

    #tool 7
def compare_sales_periods(
    first_start_date,
    first_end_date,
    second_start_date,
    second_end_date
):
    """Compare sales metrics across two date ranges."""

    first_period = get_sales_summary(
        first_start_date, first_end_date
    )

    second_period = get_sales_summary(
        second_start_date, second_end_date
    )

    first_revenue = first_period["total_revenue"]
    second_revenue = second_period["total_revenue"]

    revenue_change = round(second_revenue - first_revenue, 2)

    if first_revenue == 0:
        percentage_change = None
    else:
        percentage_change = round(
            (revenue_change / first_revenue) * 100, 2
        )

    return {
        "first_period": first_period,
        "second_period": second_period,
        "revenue_change": revenue_change,
        "revenue_change_percent": percentage_change
    }
#TOOL 8

def get_product_performance(start_date, end_date, limit=10):
    """Rank products by revenue and units sold within a date range."""

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        return {"error": "Limit must be an integer between 1 and 100"}

    if not valid_date(start_date) or not valid_date(end_date):
        return {"error": "Dates must use YYYY-MM-DD format"}

    if start_date > end_date:
        return {"error": "Start date cannot be after end date"}

    with get_connection() as connection:
        sql = """
            SELECT
                p.product_id,
                p.title,
                p.category,
                SUM(oi.quantity) AS units_sold,
                ROUND(
                    SUM(oi.quantity * oi.unit_price - oi.discount), 2
                ) AS revenue
            FROM order_items AS oi
            JOIN orders AS o
                ON oi.order_id = o.order_id
            JOIN variants AS v
                ON oi.variant_id = v.variant_id
            JOIN products AS p
                ON v.product_id = p.product_id
            WHERE o.order_date BETWEEN ? AND ?
              AND o.status != 'cancelled'
            GROUP BY p.product_id, p.title, p.category
            ORDER BY revenue DESC
            LIMIT ?
        """

        rows = connection.execute(
            sql, (start_date, end_date, limit)
        ).fetchall()

        return [dict(row) for row in rows]



               
            
           

    #tool9
    
def get_refund_summary(start_date, end_date):
    """Summarize refunds by status and reason within a date range."""

    if not valid_date(start_date) or not valid_date(end_date):
        return {"error": "Dates must use YYYY-MM-DD format"}

    if start_date > end_date:
        return {"error": "Start date cannot be after end date"}

    with get_connection() as connection:
        totals_sql = """
            SELECT
                COUNT(*) AS total_refunds,
                COALESCE(SUM(amount), 0) AS total_refund_amount
            FROM refunds
            WHERE refund_date BETWEEN ? AND ?
              AND status = 'completed'
        """

        totals_row = connection.execute(
            totals_sql, (start_date, end_date)
        ).fetchone()

        status_sql = """
            SELECT status, COUNT(*) AS count
            FROM refunds
            WHERE refund_date BETWEEN ? AND ?
            GROUP BY status
            ORDER BY count DESC
        """

        status_rows = connection.execute(
            status_sql, (start_date, end_date)
        ).fetchall()

        reason_sql = """
            SELECT
                reason,
                COUNT(*) AS count,
                ROUND(SUM(amount), 2) AS total_amount
            FROM refunds
            WHERE refund_date BETWEEN ? AND ?
              AND status = 'completed'
            GROUP BY reason
            ORDER BY count DESC
        """

        reason_rows = connection.execute(
            reason_sql, (start_date, end_date)
        ).fetchall()

        return {
            "start_date": start_date,
            "end_date": end_date,
            "completed_refund_count": totals_row["total_refunds"],
            "completed_refund_amount": round(
                totals_row["total_refund_amount"], 2
            ),
            "status_breakdown": [dict(row) for row in status_rows],
            "completed_refunds_by_reason": [
                dict(row) for row in reason_rows
            ]
        }

    

        
    #TOOL 10
    
def get_stockout_risk(limit=20):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        return {"error": "Limit must be an integer between 1 and 100"}
    """Find variants that are out of stock or at/below reorder threshold."""

    with get_connection() as connection:
        sql = """
            SELECT
                v.variant_id,
                v.product_id,
                p.title AS product_title,
                v.sku,
                v.size,
                v.color,
                i.available_units,
                i.reorder_threshold,
                i.updated_at,
                CASE
                    WHEN i.available_units = 0 THEN 'out_of_stock'
                    WHEN i.available_units <= i.reorder_threshold
                        THEN 'low_stock'
                END AS risk_level
            FROM inventory AS i
            JOIN variants AS v
                ON i.variant_id = v.variant_id
            JOIN products AS p
                ON v.product_id = p.product_id
            WHERE i.available_units <= i.reorder_threshold
            ORDER BY
                i.available_units ASC,
                i.reorder_threshold DESC
            LIMIT ?
        """

        rows = connection.execute(sql, (limit,)).fetchall()

        return [dict(row) for row in rows]

    #TOOL 11
    
def get_exchange_rate(currency):
    """Get the exchange rate from PKR to a supported currency."""

    if not isinstance(currency, str):
        return {"error": "Currency must be a string"}

    currency = currency.strip().upper()

    if currency not in ["USD", "EUR", "GBP"]:
        return {"error": "Choose USD, EUR, or GBP"}

    try:
        response = requests.get(
            f"https://api.frankfurter.dev/v2/rate/PKR/{currency}",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        rate = data.get("rate")
        rate_date = data.get("date")

        if not isinstance(rate, (int, float)) or not isinstance(rate_date, str):
            return {"error": "Unexpected exchange-rate API response"}

        return {
            "base_currency": "PKR",
            "target_currency": currency,
            "rate": rate,
            "date": rate_date
        }

    except requests.RequestException as error:
        return {"error": f"Exchange rate request failed: {error}"}

    except ValueError:
        return {"error": "Exchange-rate API returned invalid JSON"}




    #TOOL 12

def calculate_reorder_quantity(variant_id):
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                p.title,
                v.variant_id,
                v.sku,
                i.available_units,
                i.reorder_threshold
            FROM inventory AS i
            JOIN variants AS v
                ON i.variant_id = v.variant_id
            JOIN products AS p
                ON v.product_id = p.product_id
            WHERE v.variant_id = ?
        """, (variant_id,))

        row = cursor.fetchone()

        if row is None:
            return {"error": "Inventory variant not found"}

        available_stock = row["available_units"]
        target_stock = row["reorder_threshold"]

        reorder_quantity = max(
            0,
            target_stock - available_stock
        )

        return {
            "product": row["title"],
            "variant_id": row["variant_id"],
            "sku": row["sku"],
            "available_stock": available_stock,
            "target_stock": target_stock,
            "reorder_quantity": reorder_quantity
        }

    finally:
        connection.close()
    #TOOL 13


def propose_discount(product_id, discount_percent, reason):
    """Propose a discount for a product without applying it."""

    if (
        not isinstance(discount_percent, (int, float))
        or isinstance(discount_percent, bool)
        or not 0 < discount_percent <= 100
    ):
        return {
            "error": "Discount must be greater than 0 and at most 100%"
        }

    if not isinstance(reason, str) or not reason.strip():
        return {"error": "Please provide a reason for the discount"}

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT product_id, title, status
            FROM products
            WHERE product_id = ?
        """, (product_id,))

        product = cursor.fetchone()

        if product is None:
            return {"error": "Product not found"}

        cursor.execute("""
            SELECT
                MIN(price) AS min_price,
                MAX(price) AS max_price
            FROM variants
            WHERE product_id = ?
        """, (product_id,))

        prices = cursor.fetchone()

        if prices["min_price"] is None:
            return {"error": "No variant prices found for this product"}

        discount_factor = 1 - discount_percent / 100

        return {
            "product_id": product["product_id"],
            "product_name": product["title"],
            "discount_percent": discount_percent,
            "reason": reason.strip(),
            "original_price_range_pkr": {
                "min": prices["min_price"],
                "max": prices["max_price"]
            },
            "proposed_price_range_pkr": {
                "min": round(prices["min_price"] * discount_factor, 2),
                "max": round(prices["max_price"] * discount_factor, 2)
            },
            "status": "pending_approval"
        }

    finally:
        connection.close()

        #TOOL 14


def propose_inventory_alert(variant_id):
    """Check stock and save alerts for human approval when needed."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                p.title,
                v.variant_id,
                v.sku,
                i.available_units,
                i.reorder_threshold
            FROM inventory AS i
            JOIN variants AS v ON i.variant_id = v.variant_id
            JOIN products AS p ON v.product_id = p.product_id
            WHERE v.variant_id = ?
            """,
            (variant_id,),
        )

        item = cursor.fetchone()

        if item is None:
            return {"error": "Inventory variant not found"}

        available = item["available_units"]
        threshold = item["reorder_threshold"]

        if available == 0:
            alert_level = "out_of_stock"
        elif available <= threshold:
            alert_level = "low_stock"
        else:
            alert_level = "normal"

        payload = {
            "product_name": item["title"],
            "variant_id": item["variant_id"],
            "sku": item["sku"],
            "available_stock": available,
            "reorder_threshold": threshold,
            "alert_level": alert_level,
        }

    finally:
        connection.close()

    if alert_level == "normal":
        return {**payload, "status": "no_alert_needed"}

    approval = save_approval_request(
        action="propose_inventory_alert",
        payload=payload,
    )

    return {**payload, **approval, "status": "pending_approval"}


# Test Tool 
if __name__ == "__main__":
    print(
        get_product_performance(
            "2026-06-01", "2026-06-30", limit=5
        )
    )

    print(
        get_product_performance(
            "2026-06-01", "2026-06-30", limit=0
        )
    )