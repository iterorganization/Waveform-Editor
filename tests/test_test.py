import pytest


def test_pytest_succeed():
    assert 1 == 1


def test_pytest_fail():
    with pytest.raises(AssertionError):
        assert 1 == 2
