import imas
import numpy as np
import pandas as pd
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import (
    CARD_CSS,
    STYLES,
    EquilibriumInput,
    FixedWidthEditableIntSlider,
    FormattedEditableFloatSlider,
    metric_pill,
)
from waveform_editor.settings import NiceSettings, settings
from waveform_editor.shape_editor.gaps import MACHINE_GAPS
from waveform_editor.shape_editor.plasma_shape_calc import (
    apply_point_weights,
    compute_gaussian_weights,
    compute_outline_from_params,
    fit_params_to_outline,
    resample_outline,
)

# A shape to start from for each machine, taken from one of its discharges, as
# (value, slider range) per parameter
MACHINE_SHAPES = {
    NiceSettings.PRESET_ITER: {
        "a": (1.98, (1, 2.5)),
        "center_r": (6.21, (5, 7)),
        "center_z": (0.87, (0, 1.5)),
        "kappa": (1.58, (0, 3)),
        "delta": (0.41, (-1, 1)),
        "rx": (5.117, (4.5, 6)),
        "zx": (-3.414, (-4, -2)),
        "rx_upper": (5.089, (4.5, 6)),
        "zx_upper": (3.346, (2, 4)),
    },
    NiceSettings.PRESET_WEST: {
        "a": (0.46, (0.2, 0.8)),
        "center_r": (2.54, (2, 3)),
        "center_z": (-0.02, (-0.5, 0.5)),
        "kappa": (1.31, (0, 3)),
        "delta": (0.38, (-1, 1)),
        "rx": (2.23, (1.8, 3.2)),
        "zx": (-0.62, (-1.2, 0)),
        "rx_upper": (2.23, (1.8, 3.2)),
        "zx_upper": (0.62, (0, 1.2)),
    },
}


# Sliders have a fixed width, and are put side by side as far as there is room
SLIDER_WIDTH = 320


def _group(title, *children, visible=True):
    """A group of inputs under a divider and a title, without a box around it."""
    return pn.Column(
        pn.pane.HTML(
            f"<hr style='margin:4px 0 8px 0;border-color:#dee2e6;'><b>{title}</b>",
            sizing_mode="stretch_width",
            margin=0,
        ),
        pn.FlexBox(*children, margin=0),
        sizing_mode="stretch_width",
        margin=0,
        visible=visible,
    )


def _card(title, *children, visible=True):
    """A box with a title, holding one part of the panel."""
    return pn.Column(
        pn.pane.HTML(
            pn.rx(
                "<b>{}</b><hr style='margin:4px 0 8px 0;border-color:#dee2e6;'>"
            ).format(title),
            sizing_mode="stretch_width",
            margin=0,
        ),
        *children,
        css_classes=["property-card"],
        stylesheets=[CARD_CSS],
        styles={"background": "white"},
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 0),
        visible=visible,
    )


class PlasmaShapeParams(Viewer):
    """Helper class containing parameters to parameterize the plasma shape."""

    a = param.Number(
        default=1.9,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[1, 2],
        label="Minor radius",
    )
    center_r = param.Number(
        default=6.2,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[5, 7],
        label="Plasma center radius",
    )
    center_z = param.Number(
        default=0.545, step=0.01, softbounds=[0, 1.5], label="Plasma center height"
    )
    kappa = param.Number(
        default=1.8,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[0, 3],
        label="Elongation",
    )
    delta = param.Number(
        default=0.43,
        step=0.01,
        bounds=(-1, 1),
        softbounds=[-1, 1],
        label="Triangularity",
    )
    rx = param.Number(
        default=5.089,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[4.5, 6],
        label="X-point radius",
    )
    zx = param.Number(
        default=-3.346, step=0.01, softbounds=[-4, -2], label="X-point height"
    )
    second_x_point = param.Boolean(default=False, label="Second x-point")
    rx_upper = param.Number(
        default=5.089,
        step=0.01,
        bounds=(0, None),
        inclusive_bounds=(False, True),
        softbounds=[4.5, 6],
        label="Second x-point radius",
    )
    zx_upper = param.Number(
        default=3.346, step=0.01, softbounds=[2, 4], label="Second x-point height"
    )
    n_desired_bnd_points = param.Integer(
        default=100,
        bounds=(3, 5000),
        softbounds=[3, 200],
        label="Number of boundary points",
    )
    weight_enabled = param.Boolean(default=False, label="Emphasize a region")
    weight_position = param.Number(
        default=0, step=1, bounds=[0, 360], label="Position [deg]"
    )
    weight_spread = param.Number(
        default=15, step=0.5, softbounds=[1, 90], label="Spread [deg]"
    )
    weight_height = param.Integer(default=10, softbounds=[1, 1000], label="Max weight")
    extra_points_enabled = param.Boolean(
        default=False, label="Add additional weighted points"
    )
    extra_points_table = param.Parameter()

    def __init__(self, **params):
        super().__init__(**params)
        # The float sliders shown, so that their range can follow the machine
        self._sliders = {}

    def apply_machine_shape(self, values=True):
        """Start from the shape of the machine of the selected preset.

        Args:
            values: Whether to take its values, or only the ranges of the sliders.
        """
        shape = MACHINE_SHAPES.get(settings.nice.machine_preset)
        if shape is None:  # a custom machine, whose shape we cannot know
            return
        for name, (_, slider_range) in shape.items():
            if name in self.param:
                self.param[name].softbounds = slider_range
            if name in self._sliders:
                self._sliders[name].start, self._sliders[name].end = slider_range
        if not values:
            return
        self.param.update(
            **{name: value for name, (value, _) in shape.items() if name in self.param}
        )

    def _slider(self, n):
        """The widget of a parameter. The float sliders are kept, so that their
        range can follow the machine."""
        p = getattr(self.param, n)
        if isinstance(self.param[n], param.Boolean):
            return pn.widgets.Checkbox.from_param(p, sizing_mode="stretch_width")
        if isinstance(self.param[n], param.Integer):
            return FixedWidthEditableIntSlider.from_param(p, width=SLIDER_WIDTH)
        self._sliders[n] = FormattedEditableFloatSlider.from_param(
            p, width=SLIDER_WIDTH
        )
        return self._sliders[n]

    def fine_tuning(self, boundary_points=True):
        """The inputs that refine the boundary NICE is given.

        Args:
            boundary_points: Whether to include the number of boundary points, which
                only a parameterized boundary has.
        """
        _slider = self._slider
        return pn.Column(
            _group(
                "Boundary points",
                _slider("n_desired_bnd_points"),
                visible=boundary_points,
            ),
            _group(
                "Emphasized region",
                _slider("weight_enabled"),
                pn.FlexBox(
                    _slider("weight_position"),
                    _slider("weight_spread"),
                    _slider("weight_height"),
                    visible=self.param.weight_enabled.rx(),
                    sizing_mode="stretch_width",
                    margin=0,
                ),
            ),
            _group(
                "Extra points",
                _slider("extra_points_enabled"),
                pn.Row(
                    self.extra_points_table,
                    visible=self.param.extra_points_enabled.rx(),
                    sizing_mode="stretch_width",
                ),
            ),
            margin=0,
        )

    def __panel__(self):
        _slider = self._slider
        return pn.Column(
            _group(
                "Size and position",
                _slider("a"),
                _slider("center_r"),
                _slider("center_z"),
            ),
            _group(
                "Elongation and triangularity",
                _slider("kappa"),
                _slider("delta"),
                # A double null takes its shape from its x-points instead
                visible=self.param.second_x_point.rx.not_(),
            ),
            _group(
                "X-point",
                _slider("rx"),
                _slider("zx"),
                pn.Row(
                    pn.widgets.Checkbox.from_param(self.param.second_x_point),
                    pn.widgets.TooltipIcon(
                        value=(
                            "NICE inverse mode fits the target LCFS boundary points by "
                            "penalizing flux differences, but does not impose X-point "
                            "null constraints (∇ψ = 0). The resulting equilibrium is "
                            " not guaranteed to form two X-points and may produce only "
                            "1 or no X-points."
                        ),
                        align="center",
                        margin=(0, 0, 0, -10),
                    ),
                    sizing_mode="stretch_width",
                    margin=(0, 0, 5, 0),
                ),
                pn.FlexBox(
                    _slider("rx_upper"),
                    _slider("zx_upper"),
                    visible=self.param.second_x_point.rx(),
                    sizing_mode="stretch_width",
                    margin=0,
                ),
            ),
            margin=0,
        )


class WeightedPointsTable(param.Parameterized):
    """Widget for managing weighted points table for defining plasma shape."""

    COL_R = "R [m]"
    COL_Z = "Z [m]"
    COL_WEIGHT = "weight"
    MAX_WEIGHT = 5000
    COL_DELETE = "🗑️"

    points = param.DataFrame(default=pd.DataFrame(columns=[COL_R, COL_Z, COL_WEIGHT]))

    def __init__(self):
        super().__init__()
        initial_df = pd.DataFrame(
            columns=(self.COL_DELETE, self.COL_R, self.COL_Z, self.COL_WEIGHT)
        )
        self._tabulator = pn.widgets.Tabulator(
            value=initial_df,
            editors={
                self.COL_DELETE: None,
                self.COL_R: {"type": "number"},
                self.COL_Z: {"type": "number"},
                self.COL_WEIGHT: {"type": "number", "step": 1},
            },
            layout="fit_data_fill",
            sizing_mode="stretch_width",
            show_index=False,
            on_click=self._on_delete_click,
            on_edit=self._on_edit,
        )
        self._update_tabulator()

    def set_points(self, r, z, weights):
        """Replace the table contents, keeping the points in the order given.

        Args:
            r: Radial coordinates of the points.
            z: Height coordinates of the points.
            weights: How many times each point is repeated in the boundary.
        """
        rows = [
            {
                self.COL_R: round(float(rv), 3),
                self.COL_Z: round(float(zv), 3),
                self.COL_WEIGHT: self.as_weight(w),
            }
            for rv, zv, w in zip(r, z, weights, strict=True)
        ]
        self.points = pd.DataFrame(
            rows, columns=[self.COL_R, self.COL_Z, self.COL_WEIGHT]
        )
        self._update_tabulator()

    def _valid_rows(self):
        """The rows that have both coordinates filled in."""
        df = self.points.dropna(subset=[self.COL_R, self.COL_Z])
        return df[(df[self.COL_R] != "") & (df[self.COL_Z] != "")]

    def as_weight(self, value):
        """A weight as a whole number of repeats, within bounds. Points drawn on
        the plot arrive without a weight, and a weight below 1 would drop them."""
        try:
            return min(max(int(value), 1), self.MAX_WEIGHT)
        except (TypeError, ValueError):
            return 1

    def get_points(self):
        """The points entered, without weight duplication.

        Returns:
            tuple: (r, z, weights) lists, empty when no valid points are entered.
        """
        rows = self._valid_rows()
        return (
            list(rows[self.COL_R]),
            list(rows[self.COL_Z]),
            [int(w) for w in rows[self.COL_WEIGHT]],
        )

    def _update_tabulator(self, event=None):
        """Update the Tabulator to reflect the current DataFrame."""
        df = self.points
        data = []
        for _, row in df.iterrows():
            data.append(
                (
                    self.COL_DELETE,
                    row[self.COL_R],
                    row[self.COL_Z],
                    row[self.COL_WEIGHT],
                )
            )

        # Add empty row if last data row has R and Z values filled
        if len(df) == 0 or (
            df.iloc[-1][self.COL_R] != "" and df.iloc[-1][self.COL_Z] != ""
        ):
            data.append((self.COL_DELETE, "", "", 1))

        new_df = pd.DataFrame(
            data, columns=(self.COL_DELETE, self.COL_R, self.COL_Z, self.COL_WEIGHT)
        )
        # Convert columns to allow mixed types
        new_df[self.COL_R] = new_df[self.COL_R].astype(object)
        new_df[self.COL_Z] = new_df[self.COL_Z].astype(object)
        new_df[self.COL_WEIGHT] = new_df[self.COL_WEIGHT].astype(object)
        self._tabulator.value = new_df

    def _on_delete_click(self, event):
        if event.column == self.COL_DELETE:
            n_data_rows = len(self.points)
            if event.row < n_data_rows:
                df = self.points.copy()
                df = df.drop(index=event.row).reset_index(drop=True)
                self.param.update(points=df)
                self._update_tabulator()

    def _on_edit(self, event):
        """Handle edits in the weighted points tabulator."""
        df = self.points.copy()
        is_empty_row = event.row >= len(df)

        # Convert columns to object dtype to allow mixed types
        for col in [self.COL_R, self.COL_Z, self.COL_WEIGHT]:
            if col in df.columns:
                df[col] = df[col].astype(object)

        value = event.value
        if event.column == self.COL_WEIGHT:
            rounded = round(value) if value is not None else None
            if rounded is None or rounded < 1 or rounded > self.MAX_WEIGHT:
                pn.state.notifications.error(
                    f"Weight must be a whole number between 1 and {self.MAX_WEIGHT}"
                )
                prev = (
                    self.points.iloc[event.row][self.COL_WEIGHT]
                    if not is_empty_row
                    else 1
                )
                self._tabulator.value.at[event.row, self.COL_WEIGHT] = prev
                self._tabulator.param.trigger("value")
                return
            if rounded != value:
                self._tabulator.value.at[event.row, self.COL_WEIGHT] = rounded
                self._tabulator.param.trigger("value")
            value = rounded

        if is_empty_row:
            new_row = {self.COL_R: "", self.COL_Z: "", self.COL_WEIGHT: 1}
            new_row[event.column] = value
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df.at[event.row, event.column] = value

        self.points = df

        edited_row = df.iloc[event.row]
        is_last_row = event.row == len(df) - 1
        row_now_complete = edited_row[self.COL_R] != "" and edited_row[self.COL_Z] != ""
        if is_last_row and row_now_complete:
            self._update_tabulator()

    def get_outline_coordinates(self):
        """Generate outline coordinates from weighted points.

        Returns:
            tuple: (outline_r, outline_z) lists of coordinates, or (None, None) if
                no valid points have been entered yet
        """
        r, z, weights = self.get_points()
        if not r:
            return None, None
        return apply_point_weights(r, z, weights)

    def __panel__(self):
        return self._tabulator


class PlasmaShape(Viewer):
    """The target shape of the plasma that NICE is given. It starts from a reference
    shape, and is changed with the parameterisation, with gaps, or as free points."""

    EDIT_REFERENCE = "Reference shape"
    EDIT_SLIDERS = "Shape parameterisation"
    EDIT_GAPS = "Target gaps"
    EDIT_POINTS = "Free points"
    edit_by = param.Selector(
        default=EDIT_REFERENCE,
        objects=[EDIT_REFERENCE, EDIT_SLIDERS, EDIT_GAPS, EDIT_POINTS],
    )
    SOURCE_NONE = "Choose a reference…"
    SOURCE_DEFAULT = "Machine default"
    SOURCE_IDS = "Equilibrium IDS"
    SOURCE_RESULT = "Last NICE result"
    reference_source = param.Selector(
        default=SOURCE_NONE,
        objects=[SOURCE_NONE, SOURCE_DEFAULT, SOURCE_IDS, SOURCE_RESULT],
    )
    input_outline = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    # The free-form shape, and the points added on top of the parameterized one
    points_table = param.ClassSelector(
        class_=WeightedPointsTable, default=WeightedPointsTable()
    )
    extra_points_table = param.ClassSelector(
        class_=WeightedPointsTable, default=WeightedPointsTable()
    )
    shape_params = param.ClassSelector(
        class_=PlasmaShapeParams, default=PlasmaShapeParams()
    )
    last_result = param.Parameter(
        default=None, precedence=-1, doc="The equilibrium of the last NICE run."
    )
    preview = param.Parameter(
        default=None, precedence=-1, doc="The equilibrium IDS loaded, before it is set."
    )
    show_reference = param.Boolean(default=True, label="Show reference shape")
    reference_name = param.String(precedence=-1, doc="Where the reference is from.")

    has_shape = param.Boolean(doc="Whether a plasma shape is loaded.")
    shape_updated = param.Event(doc="Triggered whenever the plasma shape changes.")
    redraw = param.Event(doc="Triggered whenever what is drawn of the shape changes.")
    nice_settings = param.ClassSelector(class_=NiceSettings)

    # The shape parameters that are fitted to the gaps
    FIT_PARAMS = ("a", "center_r", "center_z", "kappa", "delta", "rx", "zx")
    # How far a fitted shape may miss what it is fitted to without a warning [m]
    FIT_TOLERANCE = 0.005

    def __init__(self):
        super().__init__(nice_settings=settings.nice)
        self.outline_r = None
        self.outline_z = None
        # Unduplicated parameterized boundary points and their per-point weight,
        # kept alongside the (possibly duplicated) outline_r/outline_z so the
        # plot can colour the boundary by weight. None when weighting is off.
        self.param_r = None
        self.param_z = None
        self.param_weights = None
        # The outline the shape was started from, drawn dashed for comparison
        self.reference_r = None
        self.reference_z = None
        self.shape_params.extra_points_table = self.extra_points_table
        # The equilibrium IDS loaded to see it before it is set, and its name
        self._preview_name = None
        self.input_outline.param.watch(self._load_preview, "load")
        # The parameterisation and free points last in sync, see _on_edit_by
        self._synced = None
        # Whether the parameterisation is still to be fitted to the reference shape
        self._fit_pending = False
        self._reference_x_point = None

        self._source_select = pn.widgets.Select.from_param(
            self.param.reference_source,
            name="",
            # "Change reference…" is only shown while no source is chosen
            stylesheets=["option:first-child { display: none; }"],
            margin=(0, 10, 8, 0),
        )
        self.gap_sliders = pn.FlexBox(margin=0)
        # The target shape is shown once a reference shape is set, and is out of the
        # way while another one is chosen
        editing = pn.bind(
            lambda name, source: bool(name) and source == self.SOURCE_NONE,
            self.param.reference_name,
            self.param.reference_source,
        )
        self.panel = pn.Column(
            _card(
                self.param.reference_name.rx().rx.pipe(
                    lambda name: (
                        f"Reference shape: {name}" if name else "Reference shape"
                    )
                ),
                pn.Row(
                    self._source_select,
                    pn.widgets.Checkbox.from_param(
                        self.param.show_reference,
                        # The reference is then the target shape itself, or the
                        # equilibrium IDS being chosen is always shown
                        disabled=pn.bind(
                            lambda edit_by, source: (
                                edit_by == self.EDIT_REFERENCE
                                or source == self.SOURCE_IDS
                            ),
                            self.param.edit_by,
                            self.param.reference_source,
                        ),
                        align="center",
                        margin=(0, 0, 8, 0),
                    ),
                    margin=0,
                ),
                pn.Column(
                    self.input_outline,
                    visible=self.param.reference_source.rx() == self.SOURCE_IDS,
                    sizing_mode="stretch_width",
                    margin=0,
                ),
                pn.widgets.Button(
                    name="Set reference shape",
                    button_type="primary",
                    disabled=self.param.reference_source.rx() == self.SOURCE_NONE,
                    margin=0,
                    on_click=self._set_reference,
                ),
            ),
            _card(
                "Target gaps",
                pn.pane.HTML(
                    self._render_gaps,
                    sizing_mode="stretch_width",
                    stylesheets=STYLES,
                    margin=0,
                ),
                visible=pn.bind(
                    lambda preset, editing: preset in MACHINE_GAPS and editing,
                    self.nice_settings.param.machine_preset,
                    editing,
                ),
            ),
            _card(
                "Target shape",
                pn.widgets.RadioButtonGroup.from_param(
                    self.param.edit_by,
                    name="",
                    button_type="primary",
                    button_style="outline",
                    stylesheets=[CARD_CSS],
                    sizing_mode="stretch_width",
                    max_width=560,
                    margin=(0, 0, 8, 0),
                ),
                self._panel_edit,
                visible=editing,
            ),
            margin=(15, 20, 12, 20),
        )
        self.param.watch(self._on_edit_by, "edit_by")
        # One event for the plot, so that it can be drawn once for several changes
        self._hold_redraw = False
        self.param.watch(
            lambda *events: self._hold_redraw or self.param.trigger("redraw"),
            [
                "shape_updated",
                "edit_by",
                "show_reference",
                "preview",
                "reference_source",
                "last_result",
            ],
        )
        self.nice_settings.param.watch(self._update_sources, "machine_preset")
        self.param.watch(self._update_sources, "last_result")
        self._update_sources()
        # Last, because clearing the shape fires the watchers above
        self.nice_settings.param.watch(self._clear_reference, "machine_preset")
        self._clear_reference()

    @pn.depends(
        "shape_params.param",
        "points_table.param",
        "extra_points_table.param",
        "edit_by",
        watch=True,
    )
    def _set_plasma_shape(self):
        """Update plasma boundary shape, triggering shape_updated only if it
        changed."""
        previous = (self.outline_r, self.outline_z, self.param_weights)
        self.param_r = self.param_z = self.param_weights = None
        if self.edit_by == self.EDIT_POINTS:
            self.outline_r, self.outline_z = self.points_table.get_outline_coordinates()
        elif self.reference_r is None:  # no reference shape is set yet
            self.outline_r = self.outline_z = None
        elif self.edit_by == self.EDIT_REFERENCE:
            self._refine_shape(
                np.asarray(self.reference_r).tolist(),
                np.asarray(self.reference_z).tolist(),
            )
        else:
            self._refine_shape(*compute_outline_from_params(**self._shape_arguments()))
        self.has_shape = bool(self.outline_r and self.outline_z)
        current = (self.outline_r, self.outline_z, self.param_weights)
        if not all(map(np.array_equal, previous, current)):
            self.param.trigger("shape_updated")

    @property
    def target_x_points(self):
        """The x-points of the target shape, which only a parameterized shape has."""
        if self.edit_by in (self.EDIT_REFERENCE, self.EDIT_POINTS):
            return []
        p = self.shape_params
        if p.second_x_point:
            return [(p.rx, p.zx), (p.rx_upper, p.zx_upper)]
        return [(p.rx, p.zx)]

    @property
    def active_points_table(self):
        """The point table the plot edits, None when no points are in use."""
        if self.edit_by == self.EDIT_POINTS:
            return self.points_table
        if self.shape_params.extra_points_enabled:
            return self.extra_points_table
        return None

    @property
    def candidate_outline(self):
        """The (r, z) of the reference shape of the chosen source, None if no source
        is chosen or it has no shape yet, such as an equilibrium IDS not loaded."""
        if self.reference_source == self.SOURCE_DEFAULT:
            shape = MACHINE_SHAPES[self.nice_settings.machine_preset]
            return compute_outline_from_params(
                **{
                    **self._shape_arguments(),
                    **{name: value for name, (value, _) in shape.items()},
                    "rx_upper": None,
                    "zx_upper": None,
                }
            )
        equilibrium = {
            self.SOURCE_RESULT: self.last_result,
            self.SOURCE_IDS: self.preview,
        }.get(self.reference_source)
        if equilibrium is None:
            return None
        outline = equilibrium.time_slice[0].boundary.outline
        return outline.r, outline.z

    def _update_sources(self, event=None):
        """Disable the sources there is nothing to take the reference from."""
        unavailable = []
        if self.nice_settings.machine_preset not in MACHINE_SHAPES:
            unavailable.append(self.SOURCE_DEFAULT)
        if self.last_result is None:
            unavailable.append(self.SOURCE_RESULT)
        if self.reference_source in unavailable:
            self.reference_source = self.SOURCE_NONE
        self._source_select.disabled_options = unavailable

    def _set_reference(self, event=None):
        """Start from the reference of the selected source."""
        # The plot is drawn once, for all that changes
        self._hold_redraw = True
        try:
            if self.reference_source == self.SOURCE_DEFAULT:
                self._start_from_default()
            elif self.reference_source == self.SOURCE_RESULT:
                self.start_from_equilibrium(self.last_result, "Last NICE result")
            elif not self._start_from_ids():
                return
            # Out of the way until the reference is changed again
            self.reference_source = self.SOURCE_NONE
        finally:
            self._hold_redraw = False
            self.param.trigger("redraw")

    def _clear_reference(self, event=None):
        """Start without a reference shape, for one to be chosen first."""
        self.shape_params.apply_machine_shape(values=False)
        self.reference_r = self.reference_z = None
        self.reference_name = ""
        self.reference_source = self.SOURCE_NONE
        self._fit_pending = False
        self.points_table.set_points([], [], [])
        self._synced = self._sync_state()
        self.edit_by = self.EDIT_REFERENCE
        self.param.trigger("edit_by")

    def _start_from_default(self, event=None):
        """Start from the shape of the machine of the selected preset."""
        preset = self.nice_settings.machine_preset
        self._fit_pending = False
        self.shape_params.apply_machine_shape()
        self.reference_r, self.reference_z = compute_outline_from_params(
            **self._shape_arguments()
        )
        self.reference_name = (
            f"{preset} default" if preset in MACHINE_SHAPES else "Default shape"
        )
        self._copy_parameterized_shape()
        self._start_editing()

    def _start_from_ids(self):
        """Start from the equilibrium IDS that is loaded.

        Returns:
            Whether an equilibrium IDS was loaded.
        """
        if self.preview is None:
            pn.state.notifications.warning("Load an equilibrium IDS first")
            return False
        self.start_from_equilibrium(self.preview, self._preview_name)
        return True

    @param.depends("reference_source", watch=True)
    def _clear_preview(self):
        """The loaded equilibrium IDS is only drawn, as the reference, while it can be
        set."""
        if self.reference_source == self.SOURCE_IDS:
            self.show_reference = True
        else:
            self.preview = None

    def _load_preview(self, event=None):
        """Load the entered equilibrium IDS, to see it on the plot before it is set."""
        try:
            with imas.DBEntry(self.input_outline.uri, "r") as entry:
                self._preview_name = (
                    f"Equilibrium IDS, t = {self.input_outline.time:g} s"
                )
                self.preview = entry.get_slice(
                    "equilibrium", self.input_outline.time, imas.ids_defs.CLOSEST_INTERP
                )
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load the equilibrium from {self.input_outline.uri}: {e}"
            )

    def start_from_equilibrium(self, equilibrium, name):
        """Start from the boundary of an equilibrium, and keep it as it is as the free
        points. The parameterisation is fitted to it once it is used.

        Args:
            equilibrium: The equilibrium IDS.
            name: What the equilibrium is, shown as the reference.
        """
        time_slice = equilibrium.time_slice[0]
        r = np.asarray(time_slice.boundary.outline.r, dtype=float)
        z = np.asarray(time_slice.boundary.outline.z, dtype=float)
        if len(r) < 3:
            pn.state.notifications.error("The equilibrium has no boundary outline")
            return
        nodes = time_slice.contour_tree.node
        # The primary x-point is node 1, see the Data Dictionary
        x_point = None
        if len(nodes) > 1 and nodes[1].critical_type == 1:
            x_point = (float(nodes[1].r), float(nodes[1].z))

        self.reference_r, self.reference_z = r, z
        self._reference_x_point = x_point
        self._fit_pending = True
        # As many points as the boundary is set to have, from the x-point on
        points_r, points_z = resample_outline(
            r,
            z,
            self.shape_params.n_desired_bnd_points,
            start=x_point or (r[z.argmin()], z.min()),
        )
        self.points_table.set_points(points_r, points_z, [1] * len(points_r))
        self.reference_name = name
        self._start_editing()

    def _fit_to_reference(self):
        """Fit the parameterisation to the reference shape of an equilibrium."""
        r, z = self.reference_r, self.reference_z
        p = self.shape_params
        fitted, distances = fit_params_to_outline(
            {"n_desired_bnd_points": p.n_desired_bnd_points},
            r,
            z,
            self._reference_x_point,
        )
        self._warn_misfit(distances, "the reference shape")
        top = z.argmax()
        p.param.update(
            **{name: fitted[name] for name in self.FIT_PARAMS},
            second_x_point=False,
            # Ready for a double null: the second x-point at the top of the outline
            rx_upper=float(r[top]),
            zx_upper=float(z[top]),
        )

    def _start_editing(self):
        """Give NICE the new reference as it is."""
        self._synced = self._sync_state()
        self._create_gap_sliders()
        self.edit_by = self.EDIT_REFERENCE
        self.param.trigger("edit_by")  # the views available depend on the machine
        self.param.trigger("shape_updated")  # the reference is drawn

    def _shape_arguments(self):
        """The arguments of compute_outline_from_params of the parameterized shape."""
        p = self.shape_params
        return dict(
            a=p.a,
            center_r=p.center_r,
            center_z=p.center_z,
            kappa=p.kappa,
            delta=p.delta,
            rx=p.rx,
            zx=p.zx,
            n_desired_bnd_points=p.n_desired_bnd_points,
            rx_upper=p.rx_upper if p.second_x_point else None,
            zx_upper=p.zx_upper if p.second_x_point else None,
        )

    def _refine_shape(self, r, z):
        """The outline NICE is given from a boundary: with its emphasized region and
        extra points."""
        p = self.shape_params
        self.param_r, self.param_z = r, z

        if p.weight_enabled:
            self.param_weights = compute_gaussian_weights(
                r, z, p.weight_position, p.weight_spread, p.weight_height
            )
            self.outline_r, self.outline_z = apply_point_weights(
                r, z, self.param_weights
            )
        else:
            self.outline_r, self.outline_z = r, z

        if p.extra_points_enabled:
            self._append_extra_points()

    def _append_extra_points(self):
        """Append the weighted points to the parameterized boundary. They go last
        because NICE measures every point against the first one, so repeats of the
        first point would cancel out."""
        extra_r, extra_z = self.extra_points_table.get_outline_coordinates()
        if not extra_r:
            return
        self.outline_r = self.outline_r + extra_r
        self.outline_z = self.outline_z + extra_z

    def _copy_parameterized_shape(self):
        """Replace the free points by the boundary of the parameterised shape."""
        r, z = compute_outline_from_params(**self._shape_arguments())
        self.points_table.set_points(r, z, [1] * len(r))

    def _fit_to_points(self):
        """Fit the parameterisation to the free points."""
        r, z, _ = self.points_table.get_points()
        if len(r) < 3:
            pn.state.notifications.error("At least 3 points are needed to fit to")
            return
        fitted, distances = fit_params_to_outline(
            {"n_desired_bnd_points": self.shape_params.n_desired_bnd_points}, r, z
        )
        self._warn_misfit(distances, "the free points")
        self.shape_params.param.update(
            **{name: fitted[name] for name in self.FIT_PARAMS}, second_x_point=False
        )

    def _warn_misfit(self, distances, fitted_to):
        """Warn when the parameterisation misses what it was fitted to."""
        if distances.max() > self.FIT_TOLERANCE:
            pn.state.notifications.warning(
                f"The shape parameterisation misses {fitted_to} by up to "
                f"{distances.max() * 100:.1f} cm"
            )

    def _sync_state(self):
        return self._shape_arguments(), self.points_table.get_points()

    def _on_edit_by(self, event):
        """Each view starts from the shape last changed in another: leaving changed
        free points fits the parameterisation to them, and a changed parameterisation
        replaces the free points. The parameterisation is fitted to the reference
        shape of an equilibrium when it is first used."""
        parameterisation, points = self._synced
        if event.old == self.EDIT_POINTS and self.points_table.get_points() != points:
            self._fit_to_points()
            self._fit_pending = False  # the free points are newer
        if event.new in (self.EDIT_SLIDERS, self.EDIT_GAPS) and self._fit_pending:
            self._fit_pending = False
            self._fit_to_reference()
        if (
            event.new == self.EDIT_POINTS
            and self._shape_arguments() != parameterisation
        ):
            self._copy_parameterized_shape()
        self._synced = self._sync_state()
        if event.new == self.EDIT_GAPS:
            if self.nice_settings.machine_preset not in MACHINE_GAPS:
                pn.state.notifications.warning(
                    "Gaps are only defined for the ITER and WEST presets"
                )
                self.edit_by = self.EDIT_SLIDERS
                return
            self._create_gap_sliders()

    @param.depends("edit_by")
    def _panel_edit(self):
        if self.edit_by == self.EDIT_REFERENCE:
            return self.shape_params.fine_tuning(boundary_points=False)
        if self.edit_by == self.EDIT_POINTS:
            return pn.Column(
                pn.widgets.Button(
                    name="Clear points",
                    icon="trash",
                    on_click=lambda event: self.points_table.set_points([], [], []),
                    margin=(8, 0),
                ),
                self.points_table,
                margin=0,
            )
        main = self.gap_sliders if self.edit_by == self.EDIT_GAPS else self.shape_params
        return pn.Column(main, self.shape_params.fine_tuning(), margin=0)

    def _shape_gaps(self, gaps, arguments):
        """The gaps of a parameterized shape, in metres by name."""
        r, z = compute_outline_from_params(**arguments)
        x_points = [(arguments["rx"], arguments["zx"])]
        return gaps.compute_gaps(r, z, **gaps.shape_inputs(x_points))

    def _create_gap_sliders(self, event=None):
        """A slider for each gap the parameterized shape can be measured on, starting
        at the gap of the current shape."""
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        self._gap_sliders = {}
        if gaps is None:
            self.gap_sliders.objects = []
            return
        for key, value in self._shape_gaps(gaps, self._shape_arguments()).items():
            if value is None:
                continue
            symbol, unit, name = gaps.GAP_METADATA[key]
            start, end = (value - 1, value + 1) if unit == "m" else (-0.1, 1)
            # In the unit the gap pills show it in
            scale = 100 if unit == "cm" else 1
            slider = FormattedEditableFloatSlider(
                name=f"{symbol}: {name} [{unit}]",
                value=value * scale,
                start=start * scale,
                end=end * scale,
                step=0.005 * scale,
                width=SLIDER_WIDTH,
            )
            slider.param.watch(self._fit_to_gaps, "value")
            self._gap_sliders[key] = slider
        self.gap_sliders.objects = list(self._gap_sliders.values())

    def _fit_to_gaps(self, event=None):
        """Set the shape parameters to those whose gaps come closest to the gap
        sliders."""
        gaps = MACHINE_GAPS[self.nice_settings.machine_preset]
        targets = {
            key: slider.value / (100 if gaps.GAP_METADATA[key][1] == "cm" else 1)
            for key, slider in self._gap_sliders.items()
        }
        ranges = {
            name: self.shape_params.param[name].softbounds for name in self.FIT_PARAMS
        }
        fitted = gaps.fit_shape(self._shape_arguments(), targets, ranges)
        self.shape_params.param.update(
            **{name: fitted[name] for name in self.FIT_PARAMS}
        )
        reached = self._shape_gaps(gaps, fitted)
        missed = {
            key: np.inf if reached.get(key) is None else abs(reached[key] - target)
            for key, target in targets.items()
        }
        worst = max(missed, key=missed.get)
        if missed[worst] > self.FIT_TOLERANCE:
            symbol = gaps.GAP_METADATA[worst][0]
            by = "" if np.isinf(missed[worst]) else f" by {missed[worst] * 100:.1f} cm"
            pn.state.notifications.warning(f"The closest shape misses {symbol}{by}")

    @param.depends("nice_settings.machine_preset", "redraw")
    def _render_gaps(self):
        """The gaps of the target shape."""
        chips = []
        gaps = MACHINE_GAPS.get(self.nice_settings.machine_preset)
        if gaps is not None and self.has_shape:
            inputs = gaps.shape_inputs(self.target_x_points)
            values = gaps.compute_gaps(self.outline_r, self.outline_z, **inputs)
            for key, (symbol, unit, name) in gaps.GAP_METADATA.items():
                value = values.get(key)
                if value is None:
                    continue
                display = f"{value:.4g} m" if unit == "m" else f"{value * 100:.3g} cm"
                chips.append(metric_pill(symbol, display, name))
        return f'<div class="mc-wrap">{"".join(chips)}</div>'

    def __panel__(self):
        return self.panel
