import imas
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


class PlasmaShape(Viewer):
    PARAMETERIZED_INPUT = "Parameterized"
    EQUILIBRIUM_INPUT = "Equilibrium IDS outline"
    GAP_INPUT = "Equilibrium IDS Gaps"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, PARAMETERIZED_INPUT, GAP_INPUT],
        label="Shape input mode",
    )
    input_outline = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
    )
    input_gaps = param.ClassSelector(
        class_=EquilibriumInput, default=EquilibriumInput()
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
            self.param.input_mode, inline=True, margin=(15, 20, 0, 20)
        )
        self.panel = pn.Column(self.radio_box, self._panel_shape_options, self.gap_ui)
        self.outline_r = None
        self.outline_z = None
        self.gaps = []

    @pn.depends(
        "shape_params.param",
        "input_outline.param",
        "input_gaps.param",
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

    def __panel__(self):
        return self.panel
