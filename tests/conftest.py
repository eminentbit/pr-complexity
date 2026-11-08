import re
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def load_single_examples():
    """Yield (name, source, expected class) for every file in examples/single."""
    for path in sorted((EXAMPLES / "single").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"#\s*expected:\s*(.+)", text)
        assert match, f"{path.name} has no '# expected:' header"
        yield path.stem, text, match.group(1).strip()


SINGLE_EXAMPLES = list(load_single_examples())


@pytest.fixture(params=SINGLE_EXAMPLES, ids=[e[0] for e in SINGLE_EXAMPLES])
def single_example(request):
    return request.param
