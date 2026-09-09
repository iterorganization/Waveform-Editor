import numpy as np
import pytest

from tests.conftest import TEST_DD_VERSION
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.points.piecewise import PiecewiseLinearTendency
from waveform_editor.tendencies.points.steps import StepsTendency
from waveform_editor.tendencies.repeat import RepeatTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.waveform import ConstantWaveform, Waveform


def test_empty():
    waveform = Waveform()
    assert waveform.tendencies == []
    assert waveform.annotations == []


@pytest.mark.parametrize(
    "entry,expected_type",
    [
        ({"user_value": 3, "user_duration": 2}, ConstantTendency),
        (
            {"user_time": [0, 1, 2], "user_value": [0, 1, 0]},
            PiecewiseLinearTendency,
        ),
        (
            {
                "user_waveform": [
                    {"user_type": "constant", "user_value": 1, "user_duration": 1}
                ],
                "user_duration": 2,
            },
            RepeatTendency,
        ),
        ({"user_to": 5, "user_duration": 2}, LinearTendency),
        ({"user_duration": 2}, LinearTendency),
    ],
    ids=["value", "time+value", "waveform", "to-only", "no-keys"],
)
def test_infer_tendency_type(entry, expected_type):
    waveform = Waveform(waveform=[entry], name="w")
    assert not waveform.annotations
    assert type(waveform.tendencies[0]) is expected_type


@pytest.fixture
def waveform_list():
    return [
        {
            "user_type": "linear",
            "user_from": 0,
            "user_to": 8,
            "user_duration": 5,
            "line_number": 1,
        },
        {
            "user_type": "sine-wave",
            "user_base": 8,
            "user_amplitude": 2,
            "user_frequency": 1,
            "user_duration": 4,
            "line_number": 2,
        },
        {
            "user_type": "constant",
            "user_value": 8,
            "user_duration": 3,
            "line_number": 3,
        },
        {
            "user_type": "smooth",
            "user_from": 8,
            "user_to": 0,
            "user_duration": 2,
            "line_number": 4,
        },
    ]


@pytest.fixture
def waveform(waveform_list):
    return Waveform(waveform=waveform_list)


def test_annotations(waveform_list):
    """Test if annotations of tendencies are passed to waveform's annotations."""
    waveform = Waveform(waveform=waveform_list)
    assert not waveform.annotations

    waveform_list[0]["type"] = "sine-wav"
    waveform = Waveform(waveform=waveform_list)
    assert waveform.annotations


def test_tendencies(waveform):
    """Test if tendencies are of correct type."""
    assert isinstance(waveform.tendencies[0], LinearTendency)
    assert isinstance(waveform.tendencies[1], SineWaveTendency)
    assert isinstance(waveform.tendencies[2], ConstantTendency)
    assert isinstance(waveform.tendencies[3], SmoothTendency)


def test_get_value(waveform):
    """Test if get_value returns the correct values."""
    times = np.linspace(0, 14, 15)
    _, values = waveform.get_value(times)
    expected = [0, 1.6, 3.2, 4.8, 6.4, 8, 8, 8, 8, 8, 8, 8, 8, 4, 0]
    assert np.allclose(values, expected)


def test_get_derivative(waveform):
    """Test if get_derivative returns the correct values."""
    times = np.linspace(0, 14, 15)
    derivatives = waveform.get_derivative(times)
    fpi = 4 * np.pi
    expected = [1.6, 1.6, 1.6, 1.6, 1.6, fpi, fpi, fpi, fpi, 0, 0, 0, 0, -6, 0]
    assert np.allclose(derivatives, expected)


def test_length(waveform):
    """Test if calc_length returns the correct value."""
    assert waveform.calc_length() == 14


def test_gap():
    """Test if gap between tendency is interpolated."""
    gap_waveform = [
        {
            "user_type": "constant",
            "user_value": 3,
            "user_start": 0,
            "user_end": 2,
            "line_number": 1,
        },
        {
            "user_type": "constant",
            "user_value": 5,
            "user_start": 4,
            "user_end": 5,
            "line_number": 2,
        },
    ]
    waveform = Waveform(waveform=gap_waveform)
    assert waveform.annotations
    times, values = waveform.get_value()
    assert np.allclose(times, [0, 2, 4, 5])
    assert np.allclose(values, [3, 3, 5, 5])

    expected = [3, 3, 3, 3, 3, 3.5, 4, 4.5, 5, 5, 5]
    _, values = waveform.get_value(np.linspace(0, 5, 11))
    assert np.allclose(values, expected)


def test_gap_derivative():
    """Test if derivative of gap between tendency is interpolated."""
    gap_waveform = [
        {
            "user_type": "linear",
            "user_from": 3,
            "user_to": 7,
            "user_start": 0,
            "user_end": 2,
            "line_number": 1,
        },
        {
            "user_type": "linear",
            "user_from": 6,
            "user_to": 3,
            "user_start": 4,
            "user_end": 5,
            "line_number": 2,
        },
    ]
    waveform = Waveform(waveform=gap_waveform)
    assert waveform.annotations

    values = waveform.get_derivative(np.linspace(0, 5, 11))
    expected = [2, 2, 2, 2, 2, -0.5, -0.5, -0.5, -3, -3, -3]
    assert np.allclose(values, expected)


def test_get_value_outside(waveform):
    """Test if values outside of range are clipped."""
    gap_waveform = [
        {
            "user_type": "constant",
            "user_value": 3,
            "user_start": 0,
            "user_end": 2,
            "line_number": 1,
        },
        {
            "user_type": "constant",
            "user_value": 5,
            "user_start": 4,
            "user_end": 5,
            "line_number": 2,
        },
    ]
    gap_waveform = Waveform(waveform=gap_waveform)
    # test requesting values outside of time range
    _, gap_values = gap_waveform.get_value(np.linspace(-1, 0, 4))
    _, values = waveform.get_value(np.linspace(-5, 0, 6))
    assert np.allclose(gap_values, [3, 3, 3, 3])
    assert np.allclose(values, np.zeros(6))

    # test requesting values outside of time range
    _, gap_values = gap_waveform.get_value(np.linspace(5, 6, 4))
    _, values = waveform.get_value(np.linspace(14, 18, 5))
    assert np.allclose(gap_values, [5, 5, 5, 5])
    assert np.allclose(values, np.zeros(5))


def test_get_derivative_outside(waveform):
    """Test if derivatives outside of range are set to zero."""
    gap_waveform = [
        {
            "user_type": "linear",
            "user_from": 3,
            "user_to": 7,
            "user_start": 0,
            "user_end": 2,
            "line_number": 1,
        },
        {
            "user_type": "linear",
            "user_from": 6,
            "user_to": 3,
            "user_start": 4,
            "user_end": 5,
            "line_number": 2,
        },
    ]
    gap_waveform = Waveform(waveform=gap_waveform)
    # test requesting values outside of time range
    gap_derivatives = gap_waveform.get_derivative(np.linspace(-1, 0, 4))
    derivatives = waveform.get_derivative(np.linspace(-5, 0, 6))
    assert np.allclose(gap_derivatives, [0, 0, 0, 2])
    assert np.allclose(derivatives, [0, 0, 0, 0, 0, 1.6])

    # test requesting values outside of time range
    gap_derivatives = gap_waveform.get_derivative(np.linspace(5, 6, 4))
    derivatives = waveform.get_derivative(np.linspace(14, 18, 5))
    assert np.allclose(gap_derivatives, [-3, 0, 0, 0])
    assert np.allclose(derivatives, np.zeros(5))


def test_overlap():
    """Test values if tendencies overlap."""
    overlap_waveform = [
        {
            "user_type": "constant",
            "user_value": 3,
            "user_start": 0,
            "user_end": 2,
            "line_number": 1,
        },
        {
            "user_type": "constant",
            "user_value": 5,
            "user_start": 1,
            "user_end": 3,
            "line_number": 2,
        },
    ]
    waveform = Waveform(waveform=overlap_waveform)
    assert waveform.annotations
    times, values = waveform.get_value()
    assert np.allclose(times, [0, 2, 1, 3])
    assert np.allclose(values, [3, 3, 5, 5])

    # Later tendencies take precedence
    expected = [3, 3, 5, 5, 5, 5, 5]
    _, values = waveform.get_value(np.linspace(0, 3, 7))
    assert np.allclose(values, expected)


def test_overlap_derivatives():
    """Test derivatives if tendencies overlap."""
    overlap_waveform = [
        {
            "user_type": "linear",
            "user_from": 3,
            "user_to": 7,
            "user_start": 0,
            "user_end": 2,
            "line_number": 1,
        },
        {
            "user_type": "linear",
            "user_from": 6,
            "user_to": 3,
            "user_start": 1,
            "user_end": 3,
            "line_number": 2,
        },
    ]
    waveform = Waveform(waveform=overlap_waveform)
    assert waveform.annotations

    # Later tendencies take precedence
    expected = [2, 2, -1.5, -1.5, -1.5, -1.5, -1.5]
    values = waveform.get_derivative(np.linspace(0, 3, 7))
    assert np.allclose(values, expected)


def test_multiple_tendencies_mixed():
    waveform = Waveform(
        waveform=[
            {
                "user_type": "constant",
                "user_value": "ec",
                "user_duration": 2,
                "line_number": 1,
            },
            {
                "user_type": "constant",
                "user_value": 3,
                "user_duration": 2,
                "line_number": 2,
            },
        ]
    )
    assert waveform.annotations


def test_steps_tendency_chained():
    """Test a steps tendency chained with a constant tendency in a waveform."""
    waveform = Waveform(
        waveform=[
            {
                "user_type": "steps",
                "user_time": [0, 2, 4, 6],
                "user_value": [1, 3, 5, 5],
                "line_number": 1,
            },
            {
                "user_type": "constant",
                "user_duration": 2,
                "line_number": 2,
            },
        ]
    )
    assert not waveform.annotations
    assert isinstance(waveform.tendencies[0], StepsTendency)
    assert isinstance(waveform.tendencies[1], ConstantTendency)
    # The constant tendency without an explicit value inherits the last step's value
    assert waveform.tendencies[1].value == 5

    times, values = waveform.get_value(np.linspace(0, 8, 9))
    assert np.allclose(values, [1, 1, 3, 3, 5, 5, 5, 5, 5])


def test_steps_tendency_string_values():
    """Test a steps tendency with string values."""
    waveform = Waveform(
        waveform=[
            {
                "user_type": "steps",
                "user_time": [0, 10, 20, 30],
                "user_value": ["ohmic", "nbi", "ec", "ec"],
                "line_number": 1,
            },
        ]
    )
    assert not waveform.annotations
    assert waveform.value_type is str
    _, values = waveform.get_value(np.array([0, 15, 25]))
    assert list(values) == ["ohmic", "nbi", "ec"]


def test_dtype_flt_dd_path():
    """Test float field types."""

    flt_dd_path = "ec_launchers/beam(1)/phase/angle"

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": "test", "line_number": 1}],
        name=flt_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 1, "line_number": 1}],
        name=flt_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert not waveform.annotations
    assert waveform.value_type is int

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 2.5, "line_number": 1}],
        name=flt_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert not waveform.annotations
    assert waveform.value_type is float


def test_dtype_int_dd_path():
    """Test int field types."""

    int_dd_path = "pulse_schedule/ec/mode"

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": "test", "line_number": 1}],
        name=int_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 1, "line_number": 1}],
        name=int_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert not waveform.annotations
    assert waveform.value_type is int

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 2.5, "line_number": 1}],
        name=int_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations


def test_dtype_str_dd_path():
    """Test string field types."""
    str_dd_path = "ec_launchers/ids_properties/comment"

    waveform = ConstantWaveform(
        waveform=[{"user_type": "constant", "user_value": "test", "line_number": 1}],
        name=str_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert not waveform.annotations
    assert waveform.value_type is str

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 1, "line_number": 1}],
        name=str_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 2.5, "line_number": 1}],
        name=str_dd_path,
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations


def test_static_0d_dd_path():
    """A constant waveform may fill a static (non time-dependent) 0D DD node."""
    waveform = ConstantWaveform(
        waveform=[
            {"user_type": "constant", "user_value": "a comment", "line_number": 1}
        ],
        name="ec_launchers/ids_properties/comment",
        dd_version=TEST_DD_VERSION,
    )
    assert not waveform.annotations


def test_static_0d_dd_path_rejects_varying_waveform():
    """A static DD node cannot hold different values at different times"""
    waveform = Waveform(
        waveform=[
            {
                "user_type": "constant",
                "user_value": "a",
                "user_duration": 1,
                "line_number": 1,
            },
            {
                "user_type": "constant",
                "user_value": "b",
                "user_duration": 1,
                "line_number": 2,
            },
        ],
        name="ec_launchers/ids_properties/comment",
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations


def test_1d_dd_path():
    """Tests 1D waveforms whose coordinate is and isn't time"""
    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 5, "line_number": 1}],
        name="ec_launchers/beam(1)/phase/angle",
        dd_version=TEST_DD_VERSION,
    )
    assert not waveform.annotations
    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 5, "line_number": 1}],
        name="core_profiles/profiles_1d/electrons/temperature",
        dd_version=TEST_DD_VERSION,
    )
    assert waveform.annotations


def test_no_metadata_allows_any_type():
    """A waveform whose path does not resolve to any DD node is not restricted
    to any particular value type."""
    name = "not_a_real_ids/path"
    waveform = Waveform(
        waveform=[
            {"user_type": "constant", "user_value": "anything", "line_number": 1}
        ],
        name=name,
    )
    assert waveform.metadata is None
    assert not waveform.annotations

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 1, "line_number": 1}],
        name=name,
    )
    assert waveform.metadata is None
    assert not waveform.annotations

    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 2.5, "line_number": 1}],
        name=name,
    )
    assert waveform.metadata is None
    assert not waveform.annotations
