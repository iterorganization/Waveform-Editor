import math

import numpy as np

from waveform_editor.gui.shape_editor.shape_editor import ITER_GAP_METRICS
from waveform_editor.settings import NiceSettings, settings
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

    # Without divertor legs the strike points are still shown, but not measured: a
    # closed boundary has no legs to measure them to
    items = compute_gap_geometry(outline_r, outline_z)
    assert len(items) == 6
    by_key = {item["key"]: item for item in items}
    for key in ("gap1", "gap2"):
        assert by_key[key]["distance"] is None
        assert by_key[key]["r_target"] == by_key[key]["r_orig"]
    for key in ("gap4", "gap5", "Rmin", "Rmax"):
        item = by_key[key]
        expected_dist = math.hypot(
            item["r_target"] - item["r_orig"],
            item["z_target"] - item["z_orig"],
        )
        assert math.isclose(item["distance"], expected_dist, rel_tol=1e-5)
        assert item["distance"] > 0

    # Rmin and Rmax are measured from r=0, at the height of the extreme point
    for key in ("Rmin", "Rmax"):
        assert by_key[key]["r_orig"] == 0.0
        assert by_key[key]["z_orig"] == by_key[key]["z_target"]
    assert math.isclose(by_key["Rmin"]["distance"], 4.2, abs_tol=1e-3)
    assert math.isclose(by_key["Rmax"]["distance"], 8.2, abs_tol=1e-3)


def test_iter_closed_separatrix_has_no_divertor_gaps():
    from waveform_editor.shape_editor.iter_gaps import compute_gaps

    theta = np.linspace(0, 2 * np.pi, 200)
    r, z = 6.2 + 2.0 * np.cos(theta), 2.0 * np.sin(theta)
    # A limited plasma: its boundary contour closes on itself
    gaps = compute_gaps(r, z, separatrix_contour=[np.column_stack([r, z])])
    assert gaps["gap1"] is None
    assert gaps["gap2"] is None


def test_iter_gaps_4_5_only_measure_towards_the_axis():
    from waveform_editor.shape_editor.plasma_shape_calc import (
        closest_outline_point,
        closest_point_facing,
    )

    # A branch 0.1 behind the point, away from the axis below it, and the plasma 1
    # towards the axis: DINA only takes the latter for gaps 4 and 5
    r = [-1.0, 1.0, 1.0, -1.0]
    z = [0.1, 0.1, -1.0, -1.0]
    assert math.isclose(closest_outline_point((0, 0), r, z, is_closed=False)[1], 0.1)
    target, distance = closest_point_facing((0, 0), r, z, (0, -10), is_closed=False)
    assert math.isclose(distance, 1.0)


def test_compute_gap_geometry_west():
    from waveform_editor.shape_editor.west_gaps import compute_gap_geometry

    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r0, z0, a = 2.5, 0.0, 0.4
    outline_r = r0 + a * np.cos(theta)
    outline_z = z0 + a * np.sin(theta)
    x_points = [(2.2, -0.6), (2.2, 0.6)]

    items = compute_gap_geometry(outline_r, outline_z, x_points)
    by_key = {item["key"]: item for item in items}
    assert set(by_key) == {
        "UROG",
        "EROG",
        "LROG",
        "RIG",
        "TIG",
        "TOG",
        "dXlow",
        "dXup",
        "dbaffle",
    }
    for item in items:
        assert item["distance"] > 0
        assert "cm" in item["distance_str"]

    # The FEEQS definitions, worked out for a circle
    def circle_r(height):
        return r0 + math.sqrt(a**2 - height**2)

    def circle_z(radius):
        return math.sqrt(a**2 - (radius - r0) ** 2)

    wall_up = 3 - 0.8 + math.sqrt(0.8**2 - 0.25**2)
    expected = {
        "UROG": wall_up - circle_r(0.25),
        "EROG": 3.0 - circle_r(0.0),
        "LROG": wall_up - circle_r(0.25),
        "RIG": (r0 - a) - 1.834,
        "TIG": 0.672 - circle_z(2.132),
        "TOG": 0.749 - circle_z(2.456),
    }
    for key, value in expected.items():
        assert math.isclose(by_key[key]["distance"], value, abs_tol=1e-4), key


def test_west_x_points_outside_the_feeqs_region_are_ignored():
    from waveform_editor.shape_editor.west_gaps import compute_gaps

    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r, z = 2.5 + 0.4 * np.cos(theta), 0.4 * np.sin(theta)
    # Below the lower divertor, where FEEQS does not look for x-points
    gaps = compute_gaps(r, z, [(2.2, -0.95), (2.2, -0.6)])
    assert math.isclose(gaps["dXlow"], compute_gaps(r, z, [(2.2, -0.6)])["dXlow"])


def test_west_first_separatrix_is_closest_in_flux_to_the_axis():
    from waveform_editor.shape_editor.west_gaps import compute_gaps

    theta = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    r, z = 2.5 + 0.4 * np.cos(theta), 0.4 * np.sin(theta)

    def contour(level):
        # Separatrices as circles, the one of the upper x-point slightly larger
        radius = 0.4 if level == -0.10 else 0.43
        t = np.linspace(0, 2 * np.pi, 400)
        return [np.column_stack([2.5 + radius * np.cos(t), radius * np.sin(t)])]

    # psi decreasing outwards from the axis; the lower x-point is the first
    x_points = [(2.2, 0.6, -0.20), (2.2, -0.6, -0.10)]
    gaps = compute_gaps(r, z, x_points, magnetic_axis=(2.5, 0.0, 0.0), contour=contour)
    assert math.isclose(gaps["dRsep"], 0.03, abs_tol=1e-3)


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
    assert hasattr(plotter, "show_desired_gaps")
    assert hasattr(plotter, "show_result_gaps")
    assert plotter.show_gaps is True
    assert plotter.show_desired_gaps is True
    assert plotter.show_result_gaps is False

    # When no shape or equilibrium is loaded, overlay is empty
    empty_overlay = plotter._plot_clearance_gaps()
    assert isinstance(empty_overlay, hv.Overlay)

    # Set up a parameterized shape for ITER
    orig_preset = settings.nice.machine_preset
    orig_mode = settings.nice.mode
    try:
        settings.nice.machine_preset = NiceSettings.PRESET_ITER
        settings.nice.mode = NiceSettings.INVERSE_MODE
        shape.has_shape = True
        shape.outline_r = [5.0, 7.0, 7.0, 5.0]
        shape.outline_z = [-1.0, -1.0, 1.0, 1.0]

        overlay = plotter._plot_clearance_gaps()
        assert isinstance(overlay, hv.Overlay)
        types = [type(el) for el in overlay.values()]
        assert hv.Points in types
        assert hv.Segments in types
        for el in overlay.values():
            if isinstance(el, (hv.Points, hv.Segments)):
                assert el.opts.get("style").kwargs["color"] == "blue"
            elif isinstance(el, hv.Labels):
                assert el.opts.get("style").kwargs["text_color"] == "blue"

        # Set up an equilibrium result, switch to result gaps
        eq = factory.equilibrium()
        eq.time_slice.resize(1)
        eq.time_slice[0].boundary.outline.r = np.array([5.0, 7.0, 7.0, 5.0])
        eq.time_slice[0].boundary.outline.z = np.array([-1.0, -1.0, 1.0, 1.0])
        eq.code.output_flag = [0]
        comm.equilibrium = eq
        plotter.show_result_gaps = True
        plotter.show_desired_gaps = False

        eq_overlay = plotter._plot_clearance_gaps()
        assert isinstance(eq_overlay, hv.Overlay)
        for el in eq_overlay.values():
            if isinstance(el, (hv.Points, hv.Segments)):
                assert el.opts.get("style").kwargs["color"] == "red"
            elif isinstance(el, hv.Labels):
                assert el.opts.get("style").kwargs["text_color"] == "red"

        # Turn on both desired gaps and result gaps simultaneously
        plotter.show_desired_gaps = True
        both_overlay = plotter._plot_clearance_gaps()
        assert isinstance(both_overlay, hv.Overlay)
        colors = {
            el.opts.get("style").kwargs.get("color")
            for el in both_overlay.values()
            if isinstance(el, (hv.Points, hv.Segments))
        }
        assert "blue" in colors and "red" in colors

        # Toggle off main show_gaps -> overlay is empty
        plotter.show_gaps = False
        off_overlay = plotter._plot_clearance_gaps()
        assert isinstance(off_overlay, hv.Overlay)
    finally:
        settings.nice.machine_preset = orig_preset
        settings.nice.mode = orig_mode


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
    orig_mode = editor.nice_settings.mode
    try:
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
    finally:
        editor.nice_settings.mode = orig_mode


def test_target_gap_pills_in_plasma_shape():
    from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape

    shape = PlasmaShape()
    # The preset is shared, so it is set back for the other tests
    orig_preset = settings.nice.machine_preset
    try:
        settings.nice.machine_preset = NiceSettings.PRESET_ITER

        # No shape loaded yet -> empty string
        assert shape._render_target_gap_pills() == ""

        # Load parameterized shape
        shape.input_mode = shape.PARAMETERIZED_INPUT
        shape._load_shape_from_params()
        assert shape.has_shape is True

        # Target gap pills rendered whenever shape is loaded
        html = shape._render_target_gap_pills()
        assert '<div class="mc-wrap">' in html
        assert "g₄" in html
        assert "g₅" in html
        assert "Rₘᵢₙ" in html
        assert "Rₘₐₓ" in html

        # Switch to WEST -> WEST pills rendered, for a WEST sized shape
        settings.nice.machine_preset = NiceSettings.PRESET_WEST
        shape.shape_params.param.update(
            a=0.46,
            center_r=2.54,
            center_z=-0.02,
            kappa=1.31,
            delta=0.38,
            rx=2.23,
            zx=-0.62,
        )
        shape._load_shape_from_params()
        west_html = shape._render_target_gap_pills()
        assert '<div class="mc-wrap">' in west_html
        for symbol in ("UROG", "EROG", "LROG", "RIG", "TIG", "TOG", "dXlow", "dbaffle"):
            assert symbol in west_html
    finally:
        settings.nice.machine_preset = orig_preset


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
    # The preset is shared, so it is set back for the other tests
    orig_preset = settings.nice.machine_preset
    try:
        settings.nice.machine_preset = NiceSettings.PRESET_ITER
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
        settings.nice.machine_preset = NiceSettings.PRESET_WEST
        assert len(shape.gaps) == 6
        assert any("UROG" in g.name for g in shape.gaps)

        # Test switching to IDS mode
        shape.gap_source = shape.GAP_SOURCE_IDS
        assert shape.gap_source == shape.GAP_SOURCE_IDS
        pane_ids = shape.panel[2]._pane
        assert "Reset Defaults" not in str(pane_ids.objects[1])
        assert shape.has_shape is False
        assert len(shape.gaps) == 0

        # Test loading equilibrium IDS with gaps
        from unittest.mock import MagicMock, patch

        mock_gap1 = MagicMock(r=4.0, z=-3.0, name="Gap1", angle=1.5, value=0.1)
        mock_gap2 = MagicMock(r=5.0, z=-4.0, name="Gap2", angle=2.0, value=0.2)
        mock_slice = MagicMock()
        mock_slice.boundary.gap = [mock_gap1, mock_gap2]
        mock_eq = MagicMock()
        mock_eq.time_slice = [mock_slice]
        mock_eq.time.tolist.return_value = [0.0]

        mock_entry = MagicMock()
        mock_entry.__enter__.return_value = mock_entry
        mock_entry.get.return_value = mock_eq
        mock_entry.get_slice.return_value = mock_eq

        with patch("imas.DBEntry", return_value=mock_entry):
            shape.input_gaps.uri = "imas:test"
            shape.input_gaps.param.trigger("load")

        assert len(shape.gaps) == 2
        assert shape.has_shape is True
        assert len(shape.gap_ui.objects) == 2

        # Test switching back to Default Gaps
        shape.gap_source = shape.GAP_SOURCE_DEFAULT
        pane_def = shape.panel[2]._pane
        assert "Reset Defaults" in str(pane_def.objects[1])
        assert len(shape.gaps) == 6
        assert shape.has_shape is True
    finally:
        # The shape keeps following the shared preset after this test, and would
        # read this URI without the mock as soon as a preset without defaults is set
        shape.input_gaps.uri = ""
        settings.nice.machine_preset = orig_preset


def test_gaps_auto_switch_on_run_finished():
    import holoviews as hv

    hv.extension("bokeh")
    from waveform_editor.configuration import WaveformConfiguration
    from waveform_editor.gui.shape_editor.shape_editor import ShapeEditor

    class MockMainGui:
        def __init__(self):
            self.config = WaveformConfiguration()

    editor = ShapeEditor(MockMainGui())
    plotter = editor.nice_plotter

    # Initially, show_gaps=True, show_desired_gaps=True, show_result_gaps=False
    assert plotter.show_gaps is True
    assert plotter.show_desired_gaps is True
    assert plotter.show_result_gaps is False

    # Simulate NICE run finished successfully
    editor._on_nice_run_finished(True)
    assert plotter.show_result_gaps is True
    assert plotter.show_desired_gaps is False

    # If show_gaps is turned off, subsettings are preserved and not auto-switched
    plotter.show_gaps = False
    plotter.show_desired_gaps = True
    plotter.show_result_gaps = False
    editor._on_nice_run_finished(True)
    assert plotter.show_desired_gaps is True
    assert plotter.show_result_gaps is False


def test_settings_modal_gap_subsettings():
    import holoviews as hv

    hv.extension("bokeh")
    from waveform_editor.configuration import WaveformConfiguration
    from waveform_editor.gui.shape_editor.settings_modal import SettingsModal
    from waveform_editor.gui.shape_editor.shape_editor import ShapeEditor

    class MockMainGui:
        def __init__(self):
            self.config = WaveformConfiguration()

    editor = ShapeEditor(MockMainGui())
    modal = SettingsModal(nice_plotter=editor.nice_plotter)

    display_tab = modal.tabs[0]
    # The gap options are nested under "Show gaps", in the visibility section
    gap_options = display_tab[1][1]

    # Shown while show_gaps is on, hidden while it is off
    assert gap_options.visible is True
    editor.nice_plotter.show_gaps = False
    assert gap_options.visible is False
    editor.nice_plotter.show_gaps = True
    assert gap_options.visible is True


def test_custom_machine_only_takes_gaps_from_an_ids():
    from waveform_editor.gui.shape_editor.plasma_shape import PlasmaShape

    # The preset is shared, so it is set back for the other tests
    orig_preset = settings.nice.machine_preset
    try:
        settings.nice.machine_preset = NiceSettings.PRESET_ITER
        shape = PlasmaShape()
        shape.input_mode = shape.GAP_INPUT
        assert len(shape.gaps) == 6

        # A custom machine has no default gaps, so there is no choice of source
        settings.nice.machine_preset = NiceSettings.PRESET_CUSTOM
        assert shape._active_gap_source == shape.GAP_SOURCE_IDS
        assert shape.gaps == []
        assert shape.gap_source_radio not in shape._panel_gap_options().objects

        # The choice for a machine with defaults is kept
        settings.nice.machine_preset = NiceSettings.PRESET_WEST
        assert shape._active_gap_source == shape.GAP_SOURCE_DEFAULT
        assert any("UROG" in gap.name for gap in shape.gaps)
    finally:
        settings.nice.machine_preset = orig_preset
