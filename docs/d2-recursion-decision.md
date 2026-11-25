# D2: how the tool handles recursion

**Decision (25 November 2026):** the tool detects recursion but does not
estimate its cost. A function that can call itself, directly or through
other functions, gets the result "unknown (recursive)" with the line of the
call. Solving simple recursion patterns moves from a Could feature to Won't
and is listed as future work.

This answers my supervisor's point from the 8 November meeting: when the depth
of a recursion depends on a variable input, its complexity cannot be
determined from the code alone.

## Evidence: recursion in CodeComplex

`experiments/recursion_survey/` parses every CodeComplex program and finds
recursive functions that the program's top-level code actually reaches.
The raw numbers are in `results.json`.

**How much:** 263 of the 4,900 programs (5.4%) run a recursive function.
Another 74 define one that is never called, usually in a template library
pasted at the top of the file, so recursion in the source often has nothing
to do with the program's label.

| Label | Programs that run recursion |
|---|---|
| O(1) | 15 of 791 (2%) |
| O(log n) | 48 of 669 (7%) |
| O(n) | 18 of 853 (2%) |
| O(n log n) | 15 of 796 (2%) |
| O(n²) | 20 of 657 (3%) |
| O(n³) | 91 of 606 (15%) |
| Exponential | 56 of 528 (11%) |

**What shape** (a program can have more than one recursive function):

| Shape | Programs | Can the cost be read from the code? |
|---|---|---|
| Memoised, or a table of visited states (`dp[i][j] != -1`, `if x in memo`, `@lru_cache`) | 113 | No: the cost is the number of distinct states times the work per state, not the number of calls |
| Shrinkage not visible (no `n - 1`, `n // 2` or half slice in the call) | 55 | No |
| Call inside a loop (depth-first search, backtracking) | 39 | No: depth and branching depend on the input data |
| Mutual recursion (f calls g, g calls f) | 7 | No |
| One call, argument halves (`f(n // 2)`, binary search) | 24 | Sometimes |
| Several calls, argument halves | 20 | Rarely, see below |
| One call, argument shrinks by a constant (`f(n - 1)`) | 6 | Usually |
| Several calls, argument shrinks by a constant | 5 | Rarely |

I checked samples of each shape by hand. Two findings matter most:

1. **Memoisation is the most common shape**, and it decides the cost. Most of
   the O(n³) recursive programs are memoised over a three-dimensional table,
   so the cost comes from the table size, not the call pattern.
2. **Counting the calls in the code gives the wrong answer for the "simple"
   patterns.** 18 of the 20 functions with several calls on a halved
   argument are labelled O(log n), because the calls sit in branches that
   exclude each other, as in a binary search (`bs_sum`), or mix `n - 1`
   with `n // 2`, as in fast exponentiation (`bin_pow`). The Master theorem
   applied to the calls as written would say O(n) for both.

Only 55 programs (1.1%) fall into a simple pattern at all, and getting even
those right would need path analysis (which calls can run together) on top
of a recurrence solver.

## Consequences

- **Analysis:** a function with a recursive call returns "unknown
  (recursive)", naming the line of the call. Loops elsewhere in the function
  are still reported in the explanation.
- **Pull request check:** if a change makes a function recursive, or changes
  a recursive call, the comment says the change cannot be assessed, rather
  than staying silent.
- **Evaluation (RQ2):** recursion is reported as a cause of "unknown" results,
  with the numbers above.
- **Scope:** "simple recursion patterns" moves from Could to Won't. Future
  work: memoised recursion could be estimated as the size of the table times
  the work per entry, when the table is created with sizes in terms of n.
- **Limitation of the survey:** shapes come from simple syntax rules, checked
  on samples rather than every program, so the numbers are close but not
  exact.
