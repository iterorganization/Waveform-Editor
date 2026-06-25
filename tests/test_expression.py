import numpy as np
import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.waveform import Waveform


@pytest.fixture
def config():
    config = WaveformConfiguration()
    config.add_group("root_group", [])
    return config


@pytest.fixture
def filled_config(config):
    waveform_list = [
        {
            "user_type": "linear",
            "user_from": 10,
            "user_to": 20,
            "user_start": 5,
            "user_end": 15,
            "line_number": 1,
        }
    ]
    waveform = Waveform(waveform=waveform_list, name="waveform/1")
    config.add_waveform(waveform, ["root_group"])
    return config


def make_expression(config, name, expr, add=True):
    """Create an expression waveform bound to ``config``."""
    waveform = Waveform(
        waveform=[{"user_expression": expr, "line_number": 0}],
        name=name,
        config=config,
    )
    if add:
        config.add_waveform(waveform, ["root_group"])
    return waveform


def test_constant_expression(config):
    waveform = make_expression(config, "waveform/1", "3")
    assert waveform.is_expression
    assert not waveform.is_categorical
    assert waveform.dependencies == set()
    _, value = waveform.get_value(np.linspace(0, 100, 101))
    assert np.all(value == 3)


def test_dependent_waveform(filled_config):
    waveform = make_expression(filled_config, "waveform/2", '"waveform/1"')
    assert waveform.dependencies == {"waveform/1"}
    time, value = waveform.get_value()
    assert time[0] == 5
    assert time[-1] == 15
    assert value[0] == 10
    assert value[-1] == 20
    _, value = waveform.get_value(np.array([0, 5, 10, 15, 20]))
    assert np.all(value == [10, 10, 15, 20, 20])


def test_dependent_waveform_calc(filled_config):
    waveform = make_expression(filled_config, "waveform/2", '"waveform/1" * 10')
    assert waveform.dependencies == {"waveform/1"}
    _, value = waveform.get_value(np.array([0, 5, 10, 15, 20]))
    assert np.all(value == [100, 100, 150, 200, 200])


def test_dependent_waveform_numpy(filled_config):
    waveform = make_expression(
        filled_config, "waveform/2", 'maximum("waveform/1" * 10, 150)'
    )
    assert waveform.dependencies == {"waveform/1"}
    _, value = waveform.get_value(np.array([0, 5, 10, 15, 20]))
    assert np.all(value == [150, 150, 150, 200, 200])


def test_rename_dependency(filled_config):
    waveform = make_expression(filled_config, "waveform/2", '"waveform/1"', add=False)
    assert waveform.dependencies == {"waveform/1"}
    waveform.rename_dependency("waveform/1", "waveform/3")
    assert waveform.dependencies == {"waveform/3"}


def test_function_access_control(filled_config):
    test_exprs = [
        ('max("waveform/1")', False),
        ('sum("waveform/1")', False),
        ('eval("waveform/1")', False),
        ('dot("waveform/1", "waveform/1")', False),
        ('linalg.norm("waveform/1")', False),
        ('linalg.inv("waveform/1")', False),
        ('sin("waveform/1")', True),
        ('log("waveform/1" + 1)', True),
        ('maximum("waveform/1", 10)', True),
    ]

    time = np.linspace(filled_config.start, filled_config.end, 100)
    for expr, allowed in test_exprs:
        waveform = make_expression(filled_config, "waveform/2", expr, add=False)
        if allowed:
            _, result = waveform.get_value(time)
            assert result is not None
        else:
            with pytest.raises(NameError):
                waveform.get_value(time)
