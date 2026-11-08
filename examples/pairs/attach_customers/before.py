# One query, then an O(n) loop.
def attach_customers(orders, db):
    names = dict(db.execute("SELECT id, name FROM customers").fetchall())
    for o in orders:
        o.customer = names[o.customer_id]
