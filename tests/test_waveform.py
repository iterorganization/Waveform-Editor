import numpy as np
import pytest

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.waveform import Waveform


def test_empty():
    waveform = Waveform()
    assert waveform.tendencies == []
    assert waveform.annotations == []


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


@pytest.mark.parametrize(
    "entry, expected",
    [
        ({"user_to": 8, "user_duration": 5}, LinearTendency),
        ({"user_time": [0, 1, 2], "user_value": [1, 2, 3]}, PiecewiseLinearTendency),
        ({"user_value": 4, "user_duration": 2}, ConstantTendency),
        # Linear does not require `to`; its other forms fall back to linear:
        ({"user_from": 3, "user_duration": 1}, LinearTendency),
        ({"user_rate": 2, "user_duration": 1}, LinearTendency),
        ({"user_duration": 1}, LinearTendency),  # bare -> linear (inferred from peers)
    ],
)
def test_infer_tendency_type(entry, expected):
    """When `type` is omitted, the tendency type is inferred from the entry's keys:
    `to` -> linear, `time` -> piecewise, `value` -> constant, else linear. Linear does
    not require `to` -- a `from`/`rate`/bare segment falls back to linear and takes its
    endpoints from its neighbours."""
    waveform = Waveform(waveform=[entry])
    assert isinstance(waveform.tendencies[0], expected)
    assert not waveform.annotations  # inference produced no errors


def test_infer_value_less_segment_is_linear():
    """A value-less segment between two constants is ambiguous from its keys alone
    (a linear ramp vs. a constant holding the previous value); inference resolves it to
    a linear ramp, so a value-less constant must set `type: constant` explicitly."""
    waveform = Waveform(
        waveform=[
            {"user_value": 3, "user_duration": 1},
            {"user_duration": 1},
            {"user_value": 10, "user_duration": 1},
        ]
    )
    assert isinstance(waveform.tendencies[1], LinearTendency)
    assert not waveform.annotations


def test_explicit_type_overrides_inference():
    """An explicit `type` is honoured even when the keys would infer another type
    (here `to` would otherwise infer linear, but `smooth` is requested)."""
    waveform = Waveform(
        waveform=[{"user_type": "smooth", "user_from": 0, "user_to": 5, "duration": 2}]
    )
    assert isinstance(waveform.tendencies[0], SmoothTendency)


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


def test_string_waveform():
    """A waveform of string constants evaluates as a zero-order-hold step function."""
    waveform = Waveform(
        waveform=[
            {"user_type": "constant", "user_value": "ohmic", "user_duration": 2},
            {"user_type": "constant", "user_value": "nbi", "user_duration": 2},
        ]
    )
    assert waveform.is_string

    _, values = waveform.get_value(np.array([0.0, 1.0, 2.0, 3.0]))
    # The switch happens at t=2; later tendencies take precedence at the boundary.
    assert list(values) == ["ohmic", "ohmic", "nbi", "nbi"]

    # Values are held (not interpolated) when extrapolating beyond the domain.
    _, extrap = waveform.get_value(np.array([-1.0, 5.0]))
    assert list(extrap) == ["ohmic", "nbi"]


def test_numeric_waveform_evaluates_to_float():
    """A numeric waveform evaluates to a float array (the int value is not stepwise)."""
    waveform = Waveform(
        waveform=[{"user_type": "constant", "user_value": 8, "user_duration": 3}]
    )
    assert not waveform.is_string
    _, values = waveform.get_value(np.array([0.0, 1.0, 2.0, 3.0]))
    assert values.dtype == float
