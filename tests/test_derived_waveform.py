import numpy as np
import pytest

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.derived_waveform import DerivedWaveform
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


@pytest.fixture
def const_waveform(config):
    name = "waveform/1"
    const_value = 3
    yaml_str = f"{name}: {const_value}"
    waveform = DerivedWaveform(yaml_str, name, config)
    config.add_waveform(waveform, ["root_group"])
    return waveform, const_value, name, config


def test_const_waveform(const_waveform):
    waveform, const_value, name, _ = const_waveform

    assert waveform.name == name
    assert waveform.yaml == const_value
    assert waveform.dependencies == set()
    assert waveform.get_yaml_string() == str(const_value)
    time = np.linspace(0, 1, 1000)
    time_ret, value_ret = waveform.get_value()
    assert np.all(time_ret == time)
    assert np.all(value_ret == const_value)
    time = np.linspace(0, 100, num=101)
    time_ret, value_ret = waveform.get_value(time)
    assert np.all(time == time_ret)
    assert np.all(value_ret == const_value)


def test_bounds(const_waveform):
    derived_waveform, const_value, _, config = const_waveform
    start = 5
    end = 15
    config.start = start
    config.end = end

    time_ret, value_ret = derived_waveform.get_value()
    assert time_ret[0] == start
    assert time_ret[-1] == end
    assert np.all(value_ret == const_value)

    _, value_ret = derived_waveform.get_value(np.array([0, 5, 10, 15]))
    assert np.all(value_ret == const_value)


def test_dependent_waveform(filled_config):
    name = "waveform/2"
    yaml_str = f"{name}: |\n  'waveform/1'"
    waveform = DerivedWaveform(yaml_str, name, filled_config)
    assert waveform.dependencies == {"waveform/1"}
    time_ret, value_ret = waveform.get_value()
    assert time_ret[0] == 5
    assert time_ret[-1] == 15
    assert value_ret[0] == 10
    assert value_ret[-1] == 20
    _, value_ret = waveform.get_value(np.array([0, 5, 10, 15, 20]))
    assert np.all(value_ret == [10, 10, 15, 20, 20])


def test_dependent_waveform_calc(filled_config):
    name = "waveform/2"
    yaml_str = f'{name}: |\n  "waveform/1" * 10'
    waveform = DerivedWaveform(yaml_str, name, filled_config)
    assert waveform.dependencies == {"waveform/1"}
    time_ret, value_ret = waveform.get_value()
    assert time_ret[0] == 5
    assert time_ret[-1] == 15
    assert value_ret[0] == 100
    assert value_ret[-1] == 200
    _, value_ret = waveform.get_value(np.array([0, 5, 10, 15, 20]))
    assert np.all(value_ret == [100, 100, 150, 200, 200])


def test_dependent_waveform_numpy(filled_config):
    name = "waveform/2"
    yaml_str = f"{name}: |\n  maximum('waveform/1' * 10, 150)"
    waveform = DerivedWaveform(yaml_str, name, filled_config)
    assert waveform.dependencies == {"waveform/1"}
    time_ret, value_ret = waveform.get_value()
    assert time_ret[0] == 5
    assert time_ret[-1] == 15
    assert value_ret[0] == 150
    assert value_ret[-1] == 200
    _, value_ret = waveform.get_value(np.array([0, 5, 10, 15, 20]))
    assert np.all(value_ret == [150, 150, 150, 200, 200])


def test_rename_waveform(filled_config):
    name = "waveform/2"
    yaml_str = f"{name}: |\n  'waveform/1'"
    waveform = DerivedWaveform(yaml_str, name, filled_config)
    assert waveform.dependencies == {"waveform/1"}
    assert waveform.get_yaml_string() == "'waveform/1'"
    waveform.rename_dependency("waveform/1", "waveform/3")
    assert waveform.dependencies == {"waveform/3"}
    assert waveform.get_yaml_string() == "'waveform/3'"


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

    for expr, allowed in test_exprs:
        name = "waveform/2"
        yaml_str = f"{name}: |\n  {expr}"
        waveform = DerivedWaveform(yaml_str, name, filled_config)
        time_ret = np.linspace(filled_config.start, filled_config.end, 100)
        if allowed:
            _, result = waveform.get_value(time_ret)
            assert result is not None
        else:
            with pytest.raises(NameError):
                waveform.get_value(time_ret)
