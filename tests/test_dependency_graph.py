import pytest

from waveform_editor.dependency_graph import DependencyGraph


def test_add_and_contains():
    dg = DependencyGraph()
    dg.add_node("A", [])
    assert "A" in dg
    assert dg.graph["A"] == set()
    dg.add_node("B", ["A"])
    assert "B" in dg
    assert "A" in dg.graph["B"]
    dg.add_node("A", ["C"])
    assert "C" in dg.graph["A"]
    dg.add_node("A", ["D"])
    assert "D" in dg.graph["A"]
    assert "C" not in dg.graph["A"]
    dg.add_node("A", ["E", "F"])
    assert "E" in dg.graph["A"]
    assert "F" in dg.graph["A"]


def test_remove_node():
    dg = DependencyGraph()
    dg.add_node("A", [])
    dg.remove_node("A")
    assert "A" not in dg


def test_check_safe_to_remove():
    dg = DependencyGraph()
    dg.add_node("A", [])
    dg.add_node("B", ["A"])
    with pytest.raises(RuntimeError):
        dg.check_safe_to_remove("A")
    dg.check_safe_to_remove("B")


def test_replace_node_no_cycle():
    dg = DependencyGraph()
    dg.add_node("A", [])
    dg.add_node("B", ["A"])
    dg.check_safe_to_replace("B", [])
    with pytest.raises(RuntimeError):
        dg.check_safe_to_replace("A", ["B"])
    dg.replace_node("B", [])
    assert dg.graph["B"] == set()


def test_replace_node_with_cycle():
    dg = DependencyGraph()
    dg.add_node("A", [])
    dg.add_node("B", ["A"])
    with pytest.raises(RuntimeError):
        dg.replace_node("A", ["B"])


def test_rename_node():
    dg = DependencyGraph()
    dg.add_node("A", [])
    dg.add_node("B", ["A"])
    dependents = dg.rename_node("A", "C")
    assert dependents == ["B"]
    assert "A" not in dg
    assert "C" in dg
    assert "C" in dg.graph["B"]


def test_detect_cycles():
    dg = DependencyGraph()
    dg.add_node("A", ["B"])
    dg.add_node("B", ["C"])
    dg.add_node("C", [])
    dg.detect_cycles()
    dg.graph["C"] = {"A"}
    with pytest.raises(RuntimeError):
        dg.detect_cycles()


def test_detect_cycles_with_start_node():
    dg = DependencyGraph()
    dg.add_node("A", ["B"])
    dg.add_node("B", ["C"])
    dg.add_node("C", [])
    dg.detect_cycles("A")
    dg.graph["C"] = {"A"}
    with pytest.raises(RuntimeError):
        dg.detect_cycles("A")
