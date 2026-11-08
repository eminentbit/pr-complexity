# Still O(n), but one query per order.
def attach_customers(orders, db):
    for o in orders:
        sql = "SELECT name FROM customers WHERE id = ?"
        o.customer = db.execute(sql, (o.customer_id,)).fetchone()
