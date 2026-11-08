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
