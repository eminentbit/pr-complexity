"""wrap_module turns a script's top-level code into one function so that
code_graph can build its graph. Cases are taken from patterns found in the
CodeComplex programs."""

import ast

import pytest

from pr_complexity.graphs import (
    MODULE_FUNCTION,
    build_graph,
    get_parser,
    has_module_code,
    split_functions,
    wrap_module,
)


def module_body(source: str) -> list[str]:
    """Wrap ``source`` and return the statement types inside __module__,
    checking on the way that nothing ended up outside it."""
    wrapped = wrap_module(source)
    ast.parse(wrapped)  # valid for CPython too, not just tree-sitter
    extras = {"comment", "line_continuation"}
    root = get_parser("python").parse(wrapped.encode()).root_node
    assert not root.has_error
    (fn,) = [c for c in root.named_children if c.type not in extras]
    assert fn.child_by_field_name("name").text.decode() == MODULE_FUNCTION
    return [c.type for c in fn.child_by_field_name("body").named_children if c.type not in extras]


def test_script_without_functions():
    source = "n = int(input())\nfor i in range(n):\n    print(i)\n"
    assert module_body(source) == ["expression_statement", "for_statement", "pass_statement"]
    graph = build_graph(wrap_module(source))
    (loop,) = graph.find("for_statement", kind="syntax")
    assert loop.line == 2 + 1  # original line 2


def test_functions_are_replaced_and_still_split():
    source = (
        "def solve(n):\n"
        "    for i in range(n):\n"
        "        print(i)\n"
        "\n"
        "solve(int(input()))\n"
    )
    assert module_body(source) == ["pass_statement", "expression_statement", "pass_statement"]
    assert build_graph(wrap_module(source)).find("for_statement") == []
    assert [f.name for f in split_functions(source)] == ["solve"]


def test_untouched_lines_keep_their_line_number():
    source = (
        "import sys\n"
        "from collections import (deque,\n"
        "                         Counter)\n"
        "@decorator\n"
        "def f():\n"
        "    return 1\n"
        "class A:\n"
        "    pass\n"
        "n = int(input())\n"
        "\n"
        "print(n)\n"
    )
    wrapped = wrap_module(source).split("\n")
    assert wrapped[0] == f"def {MODULE_FUNCTION}():"
    assert wrapped[9] == "    n = int(input())"  # original line 9 -> line 10
    assert wrapped[11] == "    print(n)"  # original line 11 -> line 12
    assert wrapped[-2] == "    pass"


def test_tabs():
    source = "n = 3\nif n:\n\tfor i in range(n):\n\t\tprint(i)\n\tprint(n)\n"
    assert module_body(source) == ["expression_statement", "if_statement", "pass_statement"]
    build_graph(wrap_module(source))


def test_statement_after_import_on_the_same_line():
    # Blanking `import sys;` with spaces left `input = ...` indented deeper
    # than the next line, and tree-sitter silently closed __module__ after it.
    source = "import sys; input = sys.stdin.readline\nn = int(input())\nprint(n)\n"
    assert module_body(source) == ["pass_statement"] + ["expression_statement"] * 3 + [
        "pass_statement"
    ]


def test_statement_after_multiline_import_on_the_same_line():
    source = "from os import (path,\n    sep); x = 1\nprint(x)\n"
    assert module_body(source) == ["pass_statement"] + ["expression_statement"] * 2 + [
        "pass_statement"
    ]


@pytest.mark.parametrize("source", [
    "import sys;\nn = int(sys.stdin.readline())\n",
    "x = input();\nprint(x)\n",
    "x = 1; y = 2;\n",
])
def test_semicolons(source):
    module_body(source)
    build_graph(wrap_module(source))


def test_main_guard_calls_main():
    source = 'def main():\n    print(1)\n\nif __name__ == "__main__":\n    main()\n'
    assert module_body(source) == ["pass_statement", "if_statement", "pass_statement"]


def test_function_defined_under_main_guard_is_removed():
    source = (
        'if __name__ == "__main__":\n'
        "    def solve(n):\n"
        "        for i in range(n):\n"
        "            print(i)\n"
        "    solve(3)\n"
    )
    module_body(source)
    assert build_graph(wrap_module(source)).find("for_statement") == []
    assert [f.name for f in split_functions(source)] == ["solve"]


@pytest.mark.parametrize("source", ["", "def f():\n    return 1", '"""Docstring."""\n'])
def test_files_with_nothing_to_run(source):
    module_body(source)
    build_graph(wrap_module(source))


def test_has_module_code():
    assert has_module_code("n = int(input())\n")
    assert has_module_code('def main():\n    pass\nif __name__ == "__main__":\n    main()\n')
    assert not has_module_code('"""Doc."""\nimport sys\n\n# note\ndef f():\n    pass\n')
    assert not has_module_code("class A:\n    pass\n")
