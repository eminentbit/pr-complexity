# expected: O(n^2)
def count_equal_pairs(xs):
    count = 0
    for a in xs:
        for b in xs:
            if a == b:
                count += 1
    return count
