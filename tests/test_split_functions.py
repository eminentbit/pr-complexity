from pr_complexity.graphs import split_functions

SOURCE = '''
import functools

def top(xs):
    return len(xs)

class OrderService:
    def total(self, orders):
        return sum(o.price for o in orders)

    @functools.lru_cache
    def cached(self, n):
        def helper(k):
            return k * 2
        return helper(n)

if True:
    def conditional():
        pass
'''


def test_finds_functions_methods_and_nested():
    names = [f.name for f in split_functions(SOURCE)]
    assert names == ["top", "OrderService.total", "OrderService.cached",
                     "OrderService.cached.helper", "conditional"]


def test_line_numbers_and_dedent():
    fns = {f.name: f for f in split_functions(SOURCE)}
    total = fns["OrderService.total"]
    assert (total.start_line, total.end_line) == (8, 9)
    assert total.source.startswith("def total(self, orders):")


# Functions under every kind of compound statement. Before this was fixed,
# defs under else/elif/except/finally/for/while/match were missed, which hid
# all the functions of 9 CodeComplex programs.
NESTED_IN_STATEMENTS = '''
try:
    from math import isqrt
except ImportError:
    def isqrt(n):
        return int(n ** 0.5)
else:
    def from_else():
        pass
finally:
    def from_finally():
        pass

if False:
    pass
elif True:
    def from_elif():
        pass
else:
    def from_if_else():
        pass

for _ in range(1):
    def from_for():
        pass
else:
    def from_for_else():
        pass

while False:
    def from_while():
        pass

with open(__file__) as f:
    def from_with():
        pass

match 1:
    case 1:
        def from_case():
            pass
'''


def test_finds_functions_under_any_statement():
    names = [f.name for f in split_functions(NESTED_IN_STATEMENTS)]
    assert names == ["isqrt", "from_else", "from_finally", "from_elif", "from_if_else",
                     "from_for", "from_for_else", "from_while", "from_with", "from_case"]


def test_finds_functions_under_main_guard():
    source = 'if __name__ == "__main__":\n    def solve():\n        pass\n    solve()\n'
    assert [f.name for f in split_functions(source)] == ["solve"]
