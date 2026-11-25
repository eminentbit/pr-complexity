# Recursion survey (D2)

Counts the CodeComplex programs whose top-level code runs a recursive
function, and sorts the recursive functions by shape. The decision it
supports is in `docs/d2-recursion-decision.md`.

```bash
python scripts/fetch_codecomplex.py          # once, if data/codecomplex/ is empty
python experiments/recursion_survey/recursion_survey.py --examples 6 > experiments/recursion_survey/results.json
```

`results.json` gives counts by label and by shape, and for each shape the ids
(row numbers in `python_data.jsonl`) of a few example programs to read.
