import pytest


# TODO: Replace placeholder tests with real tests.
def test_pytest_succeed():
    assert 1 == 1


def test_pytest_fail():
    with pytest.raises(AssertionError):
        assert 1 == 2
