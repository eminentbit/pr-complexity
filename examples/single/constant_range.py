# expected: O(1)
def first_ten(xs):
    s = 0
    for i in range(10):
        s += i
    return s
