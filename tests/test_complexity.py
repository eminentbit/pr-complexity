"""Expected complexity classes for the examples (Table 1 of the scope).

These are expected to fail until the analysis is written in weeks 4-6.
When an example starts passing, pytest reports it as XPASS.
"""

import pytest

from pr_complexity.analysis import estimate_complexity
from pr_complexity.graphs import build_graph


@pytest.mark.xfail(raises=NotImplementedError, strict=False,
                   reason="complexity analysis not implemented yet (weeks 4-6)")
def test_expected_complexity(single_example):
    name, source, expected = single_example
    assert estimate_complexity(build_graph(source)) == expected, name
