# expected: O(n)
def total(orders):
    s = 0
    for o in orders:
        s += o.price
    return s
