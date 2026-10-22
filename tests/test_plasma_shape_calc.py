import pytest

from waveform_editor.settings import NiceSettings
from waveform_editor.shape_editor.gaps import MACHINE_GAPS
from waveform_editor.shape_editor.plasma_shape_calc import (
    compute_outline_from_params,
    fit_params_to_outline,
    outline_distances,
    resample_outline,
)

# The ITER default shape
SHAPE = dict(
    a=1.98,
    center_r=6.21,
    center_z=0.87,
    kappa=1.58,
    delta=0.41,
    rx=5.117,
    zx=-3.414,
    n_desired_bnd_points=100,
    rx_upper=None,
    zx_upper=None,
)
FITTED = ("a", "center_r", "center_z", "kappa", "delta")


def test_resample_outline():
    r, z = compute_outline_from_params(**SHAPE)
    new_r, new_z = resample_outline(r, z, 40, start=(SHAPE["rx"], SHAPE["zx"]))
    assert len(new_r) == 40
    assert (new_r[0], new_z[0]) == pytest.approx((SHAPE["rx"], SHAPE["zx"]))
    assert outline_distances(new_r, new_z, r, z).max() < 1e-9


def test_fit_params_to_outline():
    r, z = compute_outline_from_params(**SHAPE)
    fitted, distances = fit_params_to_outline(r, z, 100, (SHAPE["rx"], SHAPE["zx"]))
    assert distances.max() < 1e-3
    assert [fitted[name] for name in FITTED] == pytest.approx(
        [SHAPE[name] for name in FITTED], abs=1e-2
    )


def test_fit_shape_to_gap():
    gaps = MACHINE_GAPS[NiceSettings.PRESET_ITER]
    inputs = gaps.shape_inputs([(SHAPE["rx"], SHAPE["zx"])])
    gap4 = gaps.compute_gaps(*compute_outline_from_params(**SHAPE), **inputs)["gap4"]
    ranges = {
        "a": (1, 2.5),
        "center_r": (5, 7),
        "center_z": (0, 1.5),
        "kappa": (0, 3),
        "delta": (-1, 1),
    }
    fitted = gaps.fit_shape(SHAPE, {"gap4": gap4 + 0.03}, ranges)
    reached = gaps.compute_gaps(*compute_outline_from_params(**fitted), **inputs)
    assert reached["gap4"] == pytest.approx(gap4 + 0.03, abs=5e-3)
