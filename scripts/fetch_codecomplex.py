"""Download the CodeComplex Python data at the pinned commit and verify it.

    python scripts/fetch_codecomplex.py [--dest data/codecomplex/python_data.jsonl]

The dataset's repository states no licence, so the file is downloaded here
instead of being committed (data/ is in .gitignore). The URL, commit and
SHA-256 live in pr_complexity.datasets.codecomplex.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

from pr_complexity.datasets.codecomplex import DEFAULT_PATH, SHA256, URL


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=next(iter((__doc__ or "").splitlines()), None)
    )
    parser.add_argument("--dest", default=str(DEFAULT_PATH),
                        help="where to save the file (default: %(default)s)")
    dest = Path(parser.parse_args(argv).dest)

    if dest.exists():
        if sha256_of(dest) == SHA256:
            print(f"{dest} is already present and verified")
            return 0
        print(f"{dest} exists but its SHA-256 does not match; downloading again")

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    print(f"Downloading {URL}")
    with urllib.request.urlopen(URL, timeout=60) as response, open(partial, "wb") as out:
        shutil.copyfileobj(response, out)

    actual = sha256_of(partial)
    if actual != SHA256:
        partial.unlink()
        print(f"error: SHA-256 mismatch (expected {SHA256}, got {actual})", file=sys.stderr)
        return 1
    partial.replace(dest)
    print(f"Saved {dest} (SHA-256 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
