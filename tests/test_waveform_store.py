import imas
import numpy as np
import pytest

from tests.conftest import TEST_DD_VERSION
from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.shape_editor.waveform_store import WaveformStore

ELONGATION = "equilibrium/time_slice/boundary/elongation"
IP = "equilibrium/time_slice/global_quantities/ip"
COIL_1 = "pf_active/coil(1)/current/data"


@pytest.fixture
def equilibrium():
    equilibrium = imas.IDSFactory(TEST_DD_VERSION).new("equilibrium")
    equilibrium.time_slice.resize(1)
    equilibrium.time_slice[0].boundary.elongation = 1.85
    equilibrium.time_slice[0].global_quantities.ip = -1.5e7
    equilibrium.vacuum_toroidal_field.b0 = [5.3]
    equilibrium.time_slice[0].contour_tree.node.resize(2)
    equilibrium.time_slice[0].contour_tree.node[1].r = 5.1
    equilibrium.time_slice[0].contour_tree.node[1].z = -3.3
    return equilibrium


@pytest.fixture
def pf_active():
    pf_active = imas.IDSFactory(TEST_DD_VERSION).new("pf_active")
    pf_active.coil.resize(2)
    for coil, current in zip(pf_active.coil, [100.0, 200.0], strict=True):
        coil.current.data = [current]
        coil.b_field_max_timed.data = [2.5]
        coil.force_radial.data = [1e6]
        coil.force_vertical.data = [2e6]
    return pf_active


def make_store(waveforms=""):
    config = WaveformConfiguration()
    config.load_yaml(f"globals:\n  dd_version: {TEST_DD_VERSION}\n{waveforms}")
    return WaveformStore(config)


def value_at(store, name, time):
    """The value of a waveform at a single time."""
    _, values = store.config[name].get_value(np.array([float(time)]))
    return values[0]


def test_no_quantities_without_a_run():
    assert make_store().get_quantities(None, None) == []


def test_quantities_of_a_run(equilibrium, pf_active):
    quantities = make_store().get_quantities(equilibrium, pf_active)

    by_name = {name: (group, value, units) for group, name, value, units in quantities}
    assert by_name[ELONGATION] == ("Plasma Boundary", 1.85, "1")
    assert by_name[IP] == ("Plasma Global Quantities", -1.5e7, "A")
    assert by_name[COIL_1] == ("Coil Currents", 100.0, "A")
    assert len({name for _, name, _, _ in quantities}) == len(quantities)


def test_store_creates_waveforms_per_group(equilibrium, pf_active):
    store = make_store()
    quantities = store.get_quantities(equilibrium, pf_active)

    created = store.store(quantities, 3)

    assert len(created) == len(quantities)
    assert set(store.config.groups) == set(WaveformStore.QUANTITIES)
    assert value_at(store, ELONGATION, 3) == pytest.approx(1.85)
    assert value_at(store, COIL_1, 3) == pytest.approx(100.0)


def test_store_appends_after_the_end():
    store = make_store(
        "Existing:\n"
        f"  {ELONGATION}:\n"
        "    - {type: piecewise, time: [0, 10], value: [1.0, 2.0]}\n"
    )

    created = store.store([("Plasma Boundary", ELONGATION, 1.85, "1")], 20)

    assert created == []
    assert list(store.config[ELONGATION].tendencies[-1].time) == [0, 10, 20]
    assert value_at(store, ELONGATION, 20) == pytest.approx(1.85)


def test_store_appends_after_another_tendency():
    store = make_store(
        "Existing:\n"
        f"  {ELONGATION}:\n"
        "    - {type: constant, value: 3, duration: 10}\n"
    )

    store.store([("Plasma Boundary", ELONGATION, 1.85, "1")], 20)

    assert value_at(store, ELONGATION, 20) == pytest.approx(1.85)


def test_store_refuses_a_time_the_waveform_already_covers():
    store = make_store(
        "Existing:\n"
        f"  {ELONGATION}:\n"
        "    - {type: piecewise, time: [0, 10], value: [1.0, 2.0]}\n"
    )

    with pytest.raises(ValueError, match="t=10"):
        store.store([("Plasma Boundary", ELONGATION, 1.85, "1")], 5)

    assert list(store.config[ELONGATION].tendencies[-1].time) == [0, 10]


def test_store_stops_at_the_first_waveform_it_cannot_hold():
    store = make_store(
        "Existing:\n"
        f"  {ELONGATION}:\n"
        "    - {type: piecewise, time: [0, 10], value: [1.0, 2.0]}\n"
    )
    quantities = [
        ("Plasma Boundary", ELONGATION, 1.85, "1"),
        ("Coil Currents", COIL_1, 100.0, "A"),
    ]

    with pytest.raises(ValueError):
        store.store(quantities, 5)

    # Nothing after the waveform that raised is stored
    assert COIL_1 not in store.config.waveform_map
