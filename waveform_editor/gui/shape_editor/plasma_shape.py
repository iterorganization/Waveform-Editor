import imas
import pandas as pd
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import (
    CARD_CSS,
    EquilibriumInput,
    FixedWidthEditableIntSlider,
    FormattedEditableFloatSlider,
    WarningIndicator,
)
from waveform_editor.shape_editor.plasma_shape_calc import (
    Gap,
    apply_point_weights,
    compute_gaussian_weights,
    compute_outline_from_params,
    update_outline_from_gaps,
)


class PlasmaShapeParams(Viewer):
    """Helper class containing parameters to parameterize the plasma shape."""

    a = param.Number(default=1.9, step=0.01, softbounds=[1, 2], label="Minor Radius")
    center_r = param.Number(
        default=6.2, step=0.01, softbounds=[5, 7], label="Plasma center radius"
    )
    center_z = param.Number(
        default=0.545, step=0.01, softbounds=[0, 1.5], label="Plasma center height"
    )
    kappa = param.Number(default=1.8, step=0.01, softbounds=[0, 3], label="Elongation")
    delta = param.Number(
        default=0.43, step=0.01, softbounds=[-1, 1], label="Triangularity"
    )
    rx = param.Number(
        default=5.089, step=0.01, softbounds=[4.5, 6], label="X-point radius"
    )
    zx = param.Number(
        default=-3.346, step=0.01, softbounds=[-4, -2], label="X-point height"
    )
    n_desired_bnd_points = param.Integer(
        default=96, softbounds=[3, 200], label="Number of boundary points"
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

    def __panel__(self):
        def _slider(n):
            p = getattr(self.param, n)
            if isinstance(self.param[n], param.Boolean):
                return pn.widgets.Checkbox.from_param(p)
            if isinstance(self.param[n], param.Integer):
                return FixedWidthEditableIntSlider.from_param(p, stretch_width=True)
            return FormattedEditableFloatSlider.from_param(p, stretch_width=True)

        def _group(title, *children):
            return pn.Column(
                pn.pane.HTML(
                    f"<b>{title}</b>"
                    "<hr style='margin:4px 0 8px 0;border-color:#dee2e6;'>",
                    margin=(0, 0, 0, 0),
                ),
                *children,
                css_classes=["property-card"],
                stylesheets=[CARD_CSS],
                margin=(0, 0, 8, 0),
            )

        return pn.Column(
            _group(
                "Emphasize region",
                _slider("weight_enabled"),
                pn.Column(
                    _slider("weight_position"),
                    _slider("weight_spread"),
                    _slider("weight_height"),
                    visible=self.param.weight_enabled.rx(),
                    margin=(0, 0, 0, 0),
                ),
            ),
            _group("Geometry", _slider("a"), _slider("center_r"), _slider("center_z")),
            _group("Shape coefficients", _slider("kappa"), _slider("delta")),
            _group("X point", _slider("rx"), _slider("zx")),
            _group("Boundary", _slider("n_desired_bnd_points")),
            _group(
                "Extra points",
                _slider("extra_points_enabled"),
                pn.Row(
                    self.extra_points_table,
                    visible=self.param.extra_points_enabled.rx(),
                ),
            ),
            margin=(10, 20, 0, 20),
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
    PARAMETERIZED_INPUT = "Parameterized"
    EQUILIBRIUM_INPUT = "Equilibrium IDS outline"
    GAP_INPUT = "Equilibrium IDS Gaps"
    WEIGHTED_POINTS_INPUT = "Weighted Points"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[
            EQUILIBRIUM_INPUT,
            PARAMETERIZED_INPUT,
            GAP_INPUT,
            WEIGHTED_POINTS_INPUT,
        ],
        label="Shape input mode",
    )
    input_outline = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    input_gaps = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    weighted_points_table = param.ClassSelector(
        class_=WeightedPointsTable, default=WeightedPointsTable()
    )
    shape_params = param.ClassSelector(
        class_=PlasmaShapeParams, default=PlasmaShapeParams()
    )

    has_shape = param.Boolean(doc="Whether a plasma shape is loaded.")
    shape_updated = param.Event(doc="Triggered whenever the plasma shape updates.")

    def __init__(self):
        super().__init__()

        def _indicator(tooltip):
            return WarningIndicator(
                tooltip=tooltip, visible=self.param.has_shape.rx.not_()
            )

        self.outline_indicator = _indicator(
            "No valid equilibrium IDS with outline loaded"
        )
        self.gap_indicator = _indicator("No valid equilibrium IDS with gaps loaded")
        self.weighted_points_indicator = _indicator(
            "At least 1 point is required to define a plasma shape"
        )
        self._mode_config = {
            self.EQUILIBRIUM_INPUT: (
                self._load_shape_from_ids,
                lambda: pn.Row(
                    self.input_outline,
                    self.outline_indicator,
                    margin=(10, 20, 0, 20),
                ),
            ),
            self.PARAMETERIZED_INPUT: (
                self._load_shape_from_params,
                lambda: self.shape_params,
            ),
            self.GAP_INPUT: (
                self._load_shape_from_gaps,
                lambda: pn.Row(
                    self.input_gaps, self.gap_indicator, margin=(10, 20, 0, 20)
                ),
            ),
            self.WEIGHTED_POINTS_INPUT: (
                self._load_shape_from_weighted_points,
                lambda: pn.Row(
                    self.weighted_points_table, self.weighted_points_indicator
                ),
            ),
        }
        self.gap_ui = pn.Column(visible=self.param.input_mode.rx() == self.GAP_INPUT)
        self.radio_box = pn.widgets.RadioButtonGroup(
            options={
                "Equilibrium\nIDS Outline": self.EQUILIBRIUM_INPUT,
                "Parameterized": self.PARAMETERIZED_INPUT,
                "Equilibrium\nIDS Gaps": self.GAP_INPUT,
                "Weighted\nPoints": self.WEIGHTED_POINTS_INPUT,
            },
            value=self.input_mode,
            button_type="primary",
            sizing_mode="stretch_width",
            margin=(15, 20, 0, 20),
            stylesheets=[CARD_CSS],
        )
        self.radio_box.link(self, value="input_mode", bidirectional=True)
        self.panel = pn.Column(self.radio_box, self._panel_shape_options, self.gap_ui)
        self.outline_r = None
        self.outline_z = None
        self.gaps = []
        # Unduplicated parameterized boundary points and their per-point weight,
        # kept alongside the (possibly duplicated) outline_r/outline_z so the
        # plot can colour the boundary by weight. None when weighting is off.
        self.param_r = None
        self.param_z = None
        self.param_weights = None
        self.shape_params.extra_points_table = self.weighted_points_table

    @pn.depends(
        "shape_params.param",
        "input_outline.load",
        "input_gaps.load",
        "weighted_points_table.param",
        "input_mode",
        watch=True,
    )
    def _set_plasma_shape(self):
        """Update plasma boundary shape based on input mode."""
        self.outline_r = self.outline_z = None
        self.gaps = []
        self.param_r = self.param_z = self.param_weights = None

        loader, _ = self._mode_config[self.input_mode]
        loader()

        if self.outline_r and self.outline_z:
            self.has_shape = True
        else:
            self.has_shape = False
        self.param.trigger("shape_updated")

    def _load_shape_from_ids(self):
        """Load plasma boundary outline from IDS equilibrium input."""
        if not self.input_outline.uri:
            return
        try:
            with imas.DBEntry(self.input_outline.uri, "r") as entry:
                equilibrium = entry.get_slice(
                    "equilibrium", self.input_outline.time, imas.ids_defs.CLOSEST_INTERP
                )

            self.outline_r = equilibrium.time_slice[0].boundary.outline.r
            self.outline_z = equilibrium.time_slice[0].boundary.outline.z
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load plasma boundary outline from {self.input_outline.uri}:"
                f" {str(e)}"
            )
            self.outline_r = self.outline_z = None

    def _load_shape_from_gaps(self):
        """Load plasma boundary outline from IDS equilibrium gap definitions."""
        self.gaps = []

        if self.input_gaps.uri:
            try:
                with imas.DBEntry(self.input_gaps.uri, "r") as entry:
                    equilibrium = entry.get_slice(
                        "equilibrium",
                        self.input_gaps.time,
                        imas.ids_defs.CLOSEST_INTERP,
                    )
                input_gaps = equilibrium.time_slice[0].boundary.gap
                if not input_gaps:
                    pn.state.notifications.error(
                        "The equilibrium IDS does not have any gaps"
                    )
                else:
                    for gap in input_gaps:
                        self.gaps.append(
                            Gap(
                                r=gap.r,
                                z=gap.z,
                                name=gap.name,
                                angle=gap.angle,
                                value=gap.value,
                            )
                        )
            except Exception as e:
                pn.state.notifications.error(
                    f"Could not load gaps from {self.input_gaps.uri}: {str(e)}"
                )

        self._update_outline_from_gaps()
        self._create_gap_ui()

    def _update_outline_from_gaps(self):
        """Update outline coordinates from current gap data."""
        self.outline_r, self.outline_z = update_outline_from_gaps(self.gaps)

    def _on_gap_change(self, event):
        """Callback function triggered when gap UI values change."""
        for i, value_widget in enumerate(self.gap_ui):
            self.gaps[i].value = value_widget.value
        self._update_outline_from_gaps()
        self.param.trigger("shape_updated")

    def _create_gap_ui(self):
        """Create the UI for each gap and populate the gap_ui list."""
        self.gap_ui.clear()
        if not self.gaps:
            return

        new_gap_ui = []
        for i, gap in enumerate(self.gaps):
            value_input = FormattedEditableFloatSlider(
                name=f"Gap {i}: {gap.name} Value [m]",
                value=float(gap.value),
                start=0,
                end=1,
                step=0.01,
                sizing_mode="stretch_width",
            )
            value_input.param.watch(self._on_gap_change, "value")
            new_gap_ui.append(value_input)

        self.gap_ui.extend(new_gap_ui)

    @property
    def uses_weighted_points(self):
        """Whether the weighted points table feeds the current input mode."""
        return self.input_mode == self.WEIGHTED_POINTS_INPUT or (
            self.input_mode == self.PARAMETERIZED_INPUT
            and self.shape_params.extra_points_enabled
        )

    def _load_shape_from_weighted_points(self):
        """Load plasma boundary outline from weighted points."""
        self.outline_r, self.outline_z = (
            self.weighted_points_table.get_outline_coordinates()
        )

    def _load_shape_from_params(self):
        """Compute plasma boundary outline from parameterized shape inputs."""
        p = self.shape_params
        r, z = compute_outline_from_params(
            a=p.a,
            center_r=p.center_r,
            center_z=p.center_z,
            kappa=p.kappa,
            delta=p.delta,
            rx=p.rx,
            zx=p.zx,
            n_desired_bnd_points=p.n_desired_bnd_points,
        )
        self.param_r, self.param_z = r, z

        if p.weight_enabled:
            self.param_weights = compute_gaussian_weights(
                r, z, p.weight_position, p.weight_spread, p.weight_height
            )
            self.outline_r, self.outline_z = apply_point_weights(
                r, z, self.param_weights
            )
        else:
            self.param_weights = None
            self.outline_r, self.outline_z = r, z

        if p.extra_points_enabled:
            self._append_extra_points()

    def _append_extra_points(self):
        """Append the weighted points to the parameterized boundary. They go last
        because NICE measures every point against the first one, so repeats of the
        first point would cancel out."""
        extra_r, extra_z = self.weighted_points_table.get_outline_coordinates()
        if not extra_r:
            return
        self.outline_r = self.outline_r + extra_r
        self.outline_z = self.outline_z + extra_z

    @param.depends("input_mode")
    def _panel_shape_options(self):
        _, panel_factory = self._mode_config[self.input_mode]
        return panel_factory()

    def __panel__(self):
        return self.panel
