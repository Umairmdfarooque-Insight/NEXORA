
from typing import Any


def profile_product_ids(connector: Any) -> dict[str, Any]:
    """Inspect product IDs in both tables using read-only SQL."""

    query = """
    SELECT TOP 10 product_id
    FROM saleslt.synthetic_sales_daily
    WHERE product_id IS NOT NULL;

    SELECT TOP 10 ProductID
    FROM saleslt.SalesLT_Product
    WHERE ProductID IS NOT NULL;
    """

    with connector.connect() as connection:
        cursor = connection.cursor()

        # Inspect product IDs in the sales table.
        cursor.execute("""
            SELECT TOP 10 product_id
            FROM saleslt.synthetic_sales_daily
            WHERE product_id IS NOT NULL
        """)
        sales_product_ids = [row[0] for row in cursor.fetchall()]

        # Inspect product IDs in the product dimension.
        cursor.execute("""
            SELECT TOP 10 ProductID
            FROM saleslt.SalesLT_Product
            WHERE ProductID IS NOT NULL
        """)
        dimension_product_ids = [row[0] for row in cursor.fetchall()]

    return {
        "sales_product_ids": sales_product_ids,
        "dimension_product_ids": dimension_product_ids,
    }
