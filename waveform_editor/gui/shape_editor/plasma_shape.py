import imas
import pandas as pd
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import (
    EquilibriumInput,
    FixedWidthEditableIntSlider,
    FormattedEditableFloatSlider,
    WarningIndicator,
)
from waveform_editor.shape_editor.plasma_shape_calc import (
    Gap,
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

    def __panel__(self):
        widgets = {}
        for name in self.param:
            if isinstance(self.param[name], param.Integer):
                widgets[name] = FixedWidthEditableIntSlider
            elif isinstance(self.param[name], param.Number):
                widgets[name] = FormattedEditableFloatSlider
        return pn.Param(self.param, widgets=widgets, show_name=False)


class WeightedPointsTable(param.Parameterized):
    """Widget for managing weighted points table for defining plasma shape."""

    COL_R = "R [m]"
    COL_Z = "Z [m]"
    COL_WEIGHT = "weight"
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
        self.param.watch(self._update_tabulator, "points", onlychanged=True)
        self._update_tabulator()

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
        self._tabulator.value = new_df

    def _on_delete_click(self, event):
        if event.column == self.COL_DELETE:
            n_data_rows = len(self.points)
            if event.row < n_data_rows:
                df = self.points.copy()
                df = df.drop(index=event.row).reset_index(drop=True)
                self.param.update(points=df)

    def _on_edit(self, event):
        """Handle edits in the weighted points tabulator."""
        df = self.points.copy()
        is_empty_row = event.row >= len(df)

        # Convert columns to object dtype to allow mixed types
        for col in [self.COL_R, self.COL_Z, self.COL_WEIGHT]:
            if col in df.columns:
                df[col] = df[col].astype(object)

        if event.column == self.COL_WEIGHT and (
            event.value is None or event.value < 1 or event.value > 1000
        ):
            pn.state.notifications.error("Weight must be between 1 and 1000")
            prev = (
                self.points.iloc[event.row][self.COL_WEIGHT]
                if not is_empty_row
                else 1
            )
            self._tabulator.value.at[event.row, self.COL_WEIGHT] = prev
            self._tabulator.param.trigger("value")
            return

        if is_empty_row:
            new_row = {self.COL_R: "", self.COL_Z: "", self.COL_WEIGHT: 1}
            new_row[event.column] = event.value
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
        else:
            df.at[event.row, event.column] = event.value

        self.param.update(points=df)

    def get_outline_coordinates(self):
        """Generate outline coordinates from weighted points.

        Returns:
            tuple: (outline_r, outline_z) lists of coordinates, or (None, None) if empty
        """
        if self.points.empty:
            return None, None

        # Filter out rows with empty R or Z
        valid_df = self.points.dropna(subset=[self.COL_R, self.COL_Z])
        valid_df = valid_df[(valid_df[self.COL_R] != "") & (valid_df[self.COL_Z] != "")]

        if valid_df.empty:
            return None, None

        # Duplicate points according to their weight
        outline_r = []
        outline_z = []
        for _, row in valid_df.iterrows():
            weight = row[self.COL_WEIGHT]
            outline_r.extend([row[self.COL_R]] * int(weight))
            outline_z.extend([row[self.COL_Z]] * int(weight))

        return outline_r, outline_z

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
        self.indicator = WarningIndicator(visible=self.param.has_shape.rx.not_())
        self.gap_ui = pn.Column(visible=self.param.input_mode.rx() == self.GAP_INPUT)
        self.radio_box = pn.widgets.RadioBoxGroup.from_param(
            self.param.input_mode, inline=False, margin=(15, 20, 0, 20)
        )
        self.panel = pn.Column(self.radio_box, self._panel_shape_options, self.gap_ui)
        self.outline_r = None
        self.outline_z = None
        self.gaps = []

    @pn.depends(
        "shape_params.param",
        "input_outline.param",
        "input_gaps.param",
        "weighted_points_table.param",
        "input_mode",
        watch=True,
    )
    def _set_plasma_shape(self):
        """Update plasma boundary shape based on input mode."""
        self.outline_r = self.outline_z = None
        self.gaps = []

        if self.input_mode == self.EQUILIBRIUM_INPUT:
            self._load_shape_from_ids()
        elif self.input_mode == self.PARAMETERIZED_INPUT:
            self._load_shape_from_params()
        elif self.input_mode == self.GAP_INPUT:
            self._load_shape_from_gaps()
        elif self.input_mode == self.WEIGHTED_POINTS_INPUT:
            self._load_shape_from_weighted_points()

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
                width=450,
            )
            value_input.param.watch(self._on_gap_change, "value")
            new_gap_ui.append(value_input)

        self.gap_ui.extend(new_gap_ui)

    def _load_shape_from_weighted_points(self):
        """Load plasma boundary outline from weighted points."""
        self.outline_r, self.outline_z = (
            self.weighted_points_table.get_outline_coordinates()
        )

    def _load_shape_from_params(self):
        """Compute plasma boundary outline from parameterized shape inputs."""
        self.outline_r, self.outline_z = compute_outline_from_params(
            a=self.shape_params.a,
            center_r=self.shape_params.center_r,
            center_z=self.shape_params.center_z,
            kappa=self.shape_params.kappa,
            delta=self.shape_params.delta,
            rx=self.shape_params.rx,
            zx=self.shape_params.zx,
            n_desired_bnd_points=self.shape_params.n_desired_bnd_points,
        )

    @param.depends("input_mode")
    def _panel_shape_options(self):
        if self.input_mode == self.PARAMETERIZED_INPUT:
            return self.shape_params
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            return pn.Row(pn.Param(self.input_outline, show_name=False), self.indicator)
        elif self.input_mode == self.GAP_INPUT:
            return pn.Row(pn.Param(self.input_gaps, show_name=False), self.indicator)
        elif self.input_mode == self.WEIGHTED_POINTS_INPUT:
            return self.weighted_points_table

    def __panel__(self):
        return self.panel
