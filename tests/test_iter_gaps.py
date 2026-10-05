import math

import numpy as np

from waveform_editor.gui.shape_editor.shape_editor import ITER_GAP_METRICS
from waveform_editor.shape_editor.iter_gaps import (
    GAP_POINTS,
    _distance_to_outline,
    compute_gaps,
)


def test_gap_points_defined():
    assert set(GAP_POINTS.keys()) == {"gap1", "gap2", "gap4", "gap5"}
    assert GAP_POINTS["gap1"] == (4.2230, -3.7920)
    assert GAP_POINTS["gap2"] == (5.5650, -4.4040)
    assert GAP_POINTS["gap4"] == (7.5095, 2.9971)
    assert GAP_POINTS["gap5"] == (5.3315, 4.5804)


def test_iter_gap_metrics_keys():
    expected_keys = {"gap1", "gap2", "gap4", "gap5", "Rmin", "Rmax"}
    assert set(ITER_GAP_METRICS.keys()) == expected_keys
    for key in ("gap1", "gap2", "gap4", "gap5"):
        assert ITER_GAP_METRICS[key][1] == "cm"
    for key in ("Rmin", "Rmax"):
        assert ITER_GAP_METRICS[key][1] == "m"


def test_compute_gaps_empty():
    assert compute_gaps(None, None) == {}
    assert compute_gaps([], []) == {}
    assert compute_gaps(np.array([]), np.array([])) == {}


def test_distance_to_outline_projection():
    # Outline is a square: (0, 0) -> (2, 0) -> (2, 2) -> (0, 2)
    r = [0.0, 2.0, 2.0, 0.0]
    z = [0.0, 0.0, 2.0, 2.0]

    # Point directly above bottom segment: closest point is (1, 0), dist is 0.5
    assert math.isclose(_distance_to_outline((1.0, 0.5), r, z), 0.5)

    # Point outside corner (3, 3): closest point is (2, 2), dist is sqrt(2)
    assert math.isclose(_distance_to_outline((3.0, 3.0), r, z), math.sqrt(2))


def test_compute_gaps_circular_plasma():
    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r0, z0, a = 6.2, 0.0, 2.0
    outline_r = r0 + a * np.cos(theta)
    outline_z = z0 + a * np.sin(theta)

    gaps = compute_gaps(outline_r, outline_z)
    assert set(gaps.keys()) == {"gap1", "gap2", "gap4", "gap5", "Rmin", "Rmax"}

    assert math.isclose(gaps["Rmin"], 4.2, abs_tol=1e-3)
    assert math.isclose(gaps["Rmax"], 8.2, abs_tol=1e-3)

    # Circular plasma has no divertor legs (min Z = -2.0 > -3.6)
    assert gaps["gap1"] is None
    assert gaps["gap2"] is None
    for gap_name in ("gap4", "gap5"):
        assert isinstance(gaps[gap_name], float)
        assert gaps[gap_name] > 0


def test_compute_gaps_with_separatrix_contour():
    from waveform_editor.shape_editor.iter_gaps import compute_gap_geometry

    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r0, z0, a = 6.2, 0.0, 2.0
    outline_r = r0 + a * np.cos(theta)
    outline_z = z0 + a * np.sin(theta)

    # Synthetic divertor legs passing near gap1 (4.223, -3.792) and gap2 (5.565, -4.404)
    inner_leg = np.array([[4.25, -3.75], [4.20, -3.85]])
    outer_leg = np.array([[5.55, -4.35], [5.58, -4.45]])
    contour = [inner_leg, outer_leg]
    magnetic_axis = (6.2, 0.5)

    gaps = compute_gaps(
        outline_r, outline_z, separatrix_contour=contour, magnetic_axis=magnetic_axis
    )
    for name in ("gap1", "gap2", "gap4", "gap5", "Rmin", "Rmax"):
        assert isinstance(gaps[name], float)
    assert abs(gaps["gap1"]) < 0.1  # within 10 cm of inner leg
    assert abs(gaps["gap2"]) < 0.1  # within 10 cm of outer leg

    items = compute_gap_geometry(
        outline_r, outline_z, separatrix_contour=contour, magnetic_axis=magnetic_axis
    )
    assert len(items) == 6
    symbols = {item["symbol"] for item in items}
    assert symbols == {"g₁", "g₂", "g₄", "g₅", "Rₘᵢₙ", "Rₘₐₓ"}


def test_compute_gap_geometry_empty():
    from waveform_editor.shape_editor.iter_gaps import compute_gap_geometry

    assert compute_gap_geometry(None, None) == []
    assert compute_gap_geometry([], []) == []


def test_compute_gap_geometry_iter():
    from waveform_editor.shape_editor.iter_gaps import compute_gap_geometry

    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r0, z0, a = 6.2, 0.0, 2.0
    outline_r = r0 + a * np.cos(theta)
    outline_z = z0 + a * np.sin(theta)

    # Without divertor legs: all 6 gaps are still returned
    # so strike point locations are visible
    items = compute_gap_geometry(outline_r, outline_z)
    assert len(items) == 6
    symbols = {item["symbol"] for item in items}
    assert symbols == {"g₁", "g₂", "g₄", "g₅", "Rₘᵢₙ", "Rₘₐₓ"}

    for item in items:
        expected_dist = math.hypot(
            item["r_target"] - item["r_orig"],
            item["z_target"] - item["z_orig"],
        )
        assert math.isclose(item["distance"], expected_dist, rel_tol=1e-5)
        assert item["distance"] > 0
        assert "cm" in item["distance_str"] or "m" in item["distance_str"]


def test_compute_gap_geometry_west():
    from waveform_editor.shape_editor.west_gaps import compute_gap_geometry

    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r0, z0, a = 2.5, 0.0, 0.4
    outline_r = r0 + a * np.cos(theta)
    outline_z = z0 + a * np.sin(theta)
    x_points = [(2.2, -0.6), (2.2, 0.6)]

    items = compute_gap_geometry(outline_r, outline_z, x_points)
    assert len(items) == 6
    symbols = {item["symbol"] for item in items}
    assert symbols == {"UROG", "EROG", "LROG", "dXlow", "dXup", "dbaffle"}

    for item in items:
        assert item["distance"] > 0
        assert "cm" in item["distance_str"]


def test_nice_plotter_gap_visualization():
    import holoviews as hv

    hv.extension("bokeh")
    import imas

    from waveform_editor.gui.shape_editor.nice_plotter import NicePlotter
    from waveform_editor.gui.shape_editor.plasma_properties import PlasmaProperties
    from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape
    from waveform_editor.settings import NiceSettings, settings
    from waveform_editor.shape_editor.nice_integration import NiceIntegration

    factory = imas.IDSFactory()
    comm = NiceIntegration(
        factory, on_output=lambda x: None, on_run_finished=lambda x: None
    )
    shape = PlasmaShape()
    props = PlasmaProperties()
    plotter = NicePlotter(
        communicator=comm, plasma_shape=shape, plasma_properties=props
    )

    assert hasattr(plotter, "show_gaps")
    assert plotter.show_gaps is True

    # When no shape or equilibrium is loaded, overlay is empty
    empty_overlay = plotter._plot_clearance_gaps()
    assert isinstance(empty_overlay, hv.Overlay)

    # Set up a parameterized shape for ITER
    settings.nice.machine_preset = NiceSettings.PRESET_ITER
    shape.outline_r = [5.0, 7.0, 7.0, 5.0]
    shape.outline_z = [-1.0, -1.0, 1.0, 1.0]

    overlay = plotter._plot_clearance_gaps()
    assert isinstance(overlay, hv.Overlay)
    # Check that overlay contains Points and Segments
    types = [type(el) for el in overlay.values()]
    assert hv.Points in types
    assert hv.Segments in types

    # Toggle off show_gaps
    plotter.show_gaps = False
    off_overlay = plotter._plot_clearance_gaps()
    assert isinstance(off_overlay, hv.Overlay)


def test_auto_enable_warm_start_on_direct_mode():
    import holoviews as hv

    hv.extension("bokeh")
    from waveform_editor.configuration import WaveformConfiguration
    from waveform_editor.gui.shape_editor.shape_editor import ShapeEditor
    from waveform_editor.settings import NiceSettings

    class MockMainGui:
        def __init__(self):
            self.config = WaveformConfiguration()

    editor = ShapeEditor(MockMainGui())
    editor.nice_settings.mode = NiceSettings.INVERSE_MODE
    editor.use_previous_run = False
    editor.communicator.converged = False

    # 1. Switch to direct mode without any previous run -> remains False
    editor.nice_settings.mode = NiceSettings.DIRECT_MODE
    assert editor.use_previous_run is False

    # 2. Switch back to inverse mode
    editor.nice_settings.mode = NiceSettings.INVERSE_MODE
    assert editor.use_previous_run is False

    # 3. Previous run converges
    editor.communicator.converged = True

    # 4. Switch to direct mode with converged run -> automatically True
    editor.nice_settings.mode = NiceSettings.DIRECT_MODE
    assert editor.use_previous_run is True


def test_target_gap_pills_in_plasma_shape():
    from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape

    shape = PlasmaShape()
    shape.machine_preset = "ITER"
    shape.show_gaps = True

    # No shape loaded yet -> empty string
    assert shape._render_target_gap_pills() == ""

    # Load parameterized shape
    shape.input_mode = shape.PARAMETERIZED_INPUT
    shape._load_shape_from_params()
    assert shape.has_shape is True

    # With show_gaps=True and ITER -> pills rendered
    html = shape._render_target_gap_pills()
    assert '<div class="mc-wrap">' in html
    assert "g₄" in html
    assert "g₅" in html
    assert "Rₘᵢₙ" in html
    assert "Rₘₐₓ" in html

    # With show_gaps=False -> no pills rendered
    shape.show_gaps = False
    assert shape._render_target_gap_pills() == ""

    # Switch to WEST -> WEST pills rendered
    shape.show_gaps = True
    shape.machine_preset = "WEST"
    west_html = shape._render_target_gap_pills()
    assert '<div class="mc-wrap">' in west_html
    assert "UROG" in west_html
    assert "EROG" in west_html


def test_gaps_input_mode_default_machine_gaps():
    from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape
    from waveform_editor.shape_editor.iter_gaps import get_default_iter_gaps
    from waveform_editor.shape_editor.west_gaps import get_default_west_gaps

    # Test default gaps generators directly
    iter_gaps = get_default_iter_gaps()
    assert len(iter_gaps) == 6
    assert iter_gaps[0].name == "Inner divertor leg (g₁)"
    assert iter_gaps[1].name == "Outer divertor leg (g₂)"
    assert iter_gaps[0].value == 0.0
    assert iter_gaps[1].value == 0.0

    west_gaps = get_default_west_gaps()
    assert len(west_gaps) == 6
    assert any("UROG" in g.name for g in west_gaps)
    assert any("dXlow" in g.name for g in west_gaps)

    # Test PlasmaShape in Gaps mode
    shape = PlasmaShape()
    shape.machine_preset = "ITER"
    shape.input_mode = shape.GAP_INPUT

    # Default gap source is Default Gaps
    assert shape.gap_source == shape.GAP_SOURCE_DEFAULT
    assert shape.has_shape is True
    assert len(shape.gaps) == 6
    assert len(shape.gap_ui) == 6

    # Test changing a gap slider value
    orig_val = shape.gap_ui[0].value
    shape.gap_ui[0].value = 0.05
    assert math.isclose(shape.gaps[0].value, 0.05)

    # Test reset defaults
    shape._on_reset_default_gaps()
    assert math.isclose(shape.gaps[0].value, orig_val)

    # Test switching to WEST preset
    shape.machine_preset = "WEST"
    assert len(shape.gaps) == 6
    assert any("UROG" in g.name for g in shape.gaps)

    # Test switching to IDS mode
    shape.gap_source = shape.GAP_SOURCE_IDS
    assert shape.gap_source == shape.GAP_SOURCE_IDS
