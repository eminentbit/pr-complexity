import pytest

from pr_complexity import evaluation
from pr_complexity.evaluation import Prediction, predict_program, summarise

SCRIPT = "n = int(input())\nfor i in range(n):\n    print(i)\n"


def test_unknown_while_analysis_is_not_implemented(monkeypatch):
    def not_yet(graph):
        raise NotImplementedError

    monkeypatch.setattr(evaluation, "estimate_complexity", not_yet)
    assert predict_program(SCRIPT) == "unknown"


def test_prediction_comes_from_the_wrapped_module(monkeypatch):
    seen = []

    def fake(graph):
        seen.append(graph)
        return "O(n)"

    monkeypatch.setattr(evaluation, "estimate_complexity", fake)
    assert predict_program(SCRIPT) == "O(n)"
    (graph,) = seen
    assert graph.find("for_statement", kind="syntax")


def test_invalid_class_is_an_error(monkeypatch):
    monkeypatch.setattr(evaluation, "estimate_complexity", lambda graph: "O(n!)")
    with pytest.raises(ValueError, match="O\\(n!\\)"):
        predict_program(SCRIPT)


def test_syntax_error_is_unknown(monkeypatch):
    monkeypatch.setattr(evaluation, "estimate_complexity", lambda graph: "O(1)")
    assert predict_program("for i in range(:\n") == "unknown"


def pred(problem, label, predicted):
    return Prediction(program_id=0, problem=problem, group="no functions",
                      label=label, predicted=predicted)


def test_summarise():
    s = summarise([
        pred("A", "O(n)", "O(n)"),
        pred("A", "O(n)", "O(n)"),
        pred("A", "O(n)", "unknown"),
        pred("B", "O(1)", "O(n)"),
    ])
    assert (s.programs, s.problems, s.correct, s.answered) == (4, 2, 2, 3)
    assert s.accuracy == 0.5
    assert s.coverage == 0.75
    assert s.answered_accuracy == 2 / 3
    assert s.problem_accuracy == (2 / 3 + 0) / 2  # each problem counts once
    assert s.confusion[("O(1)", "O(n)")] == 1


def test_summarise_nothing():
    s = summarise([])
    assert (s.accuracy, s.coverage, s.answered_accuracy, s.problem_accuracy) == (0, 0, 0, 0)
