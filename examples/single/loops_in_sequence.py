# expected: O(n^2)
def summary(xs):
    total = 0
    for x in xs:
        total += x
    pairs = 0
    for a in xs:
        for b in xs:
            pairs += a * b
    return total, pairs
