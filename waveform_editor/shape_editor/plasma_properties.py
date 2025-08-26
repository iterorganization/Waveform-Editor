import imas
import numpy as np
import panel as pn
import param
import scipy
from panel.viewable import Viewer

from waveform_editor.gui.util import EquilibriumInput, FormattedEditableFloatSlider


class PlasmaPropertiesParams(param.Parameterized):
    """Helper class containing parameters defining the plasma properties."""

    ip = param.Number(
        default=-1.5e7, softbounds=[-1.7e7, 0], label="Plasma current [A]"
    )
    r0 = param.Number(
        default=6.2, softbounds=[5, 7], label="Reference major radius [m]"
    )
    b0 = param.Number(
        default=-5.3, softbounds=[-10, 10], label="Toroidal field at R0 [T]"
    )
    alpha = param.Number(default=2, softbounds=[0, 10], label="Alpha")
    beta = param.Number(default=0.6, step=0.01, softbounds=[-10, 10], label="Beta")
    gamma = param.Number(default=1.4, softbounds=[0, 10], label="Gamma")


class PlasmaProperties(Viewer):
    MANUAL_INPUT = "Manual"
    EQUILIBRIUM_INPUT = "Equilibrium IDS"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, MANUAL_INPUT],
        label="Plasma properties input mode",
    )

    input = param.ClassSelector(class_=EquilibriumInput, default=EquilibriumInput())
    properties_params = param.ClassSelector(
        class_=PlasmaPropertiesParams, default=PlasmaPropertiesParams()
    )

    profile_updated = param.Event(
        doc="Triggered whenever the dpressure_dpsi and f_df_dpsi are updated."
    )
    has_properties = param.Boolean(doc="Whether the plasma properties are loaded.")

    def __init__(self):
        super().__init__()
        self.radio_box = pn.widgets.RadioBoxGroup.from_param(
            self.param.input_mode, inline=True, margin=(15, 20, 0, 20)
        )
        self.panel = pn.Column(self.radio_box, self._panel_property_options)
        self.dpressure_dpsi = None
        self.f_df_dpsi = None
        self.psi_norm = None
        self.ip = None
        self.r0 = None
        self.b0 = None

    @param.depends(
        "properties_params.param", "input.param", "input_mode", watch=True, on_init=True
    )
    def _load_plasma_properties(self):
        """Update plasma properties based on input mode."""

        if self.input_mode == self.EQUILIBRIUM_INPUT:
            self._load_properties_from_ids()
        elif self.input_mode == self.MANUAL_INPUT:
            self._load_properties_from_params()

        self.param.trigger("profile_updated")

    def _load_properties_from_params(self):
        """Load the plasma properties from the properties parameters. Calculate
        dpressure_dpsi and f_df_dpsi from the parameteric alpha, beta, and gamma
        parameters."""
        self.ip = self.properties_params.ip
        self.r0 = self.properties_params.r0
        self.b0 = self.properties_params.b0
        alpha = self.properties_params.alpha
        beta = self.properties_params.beta
        gamma = self.properties_params.gamma

        self.psi_norm = np.linspace(0, 1, 200)
        self.dpressure_dpsi = beta / self.r0 * (1 - self.psi_norm**alpha) ** gamma
        mu_0 = scipy.constants.mu_0
        self.f_df_dpsi = (
            (1 - beta) * mu_0 * self.r0 * (1 - self.psi_norm**alpha) ** gamma
        )
        self.has_properties = True

    def _load_properties_from_ids(self):
        """Load plasma properties from IDS equilibrium input."""
        if not self.input.uri:
            self.has_properties = False
            return
        try:
            with imas.DBEntry(self.input.uri, "r") as entry:
                equilibrium = entry.get_slice(
                    "equilibrium", self.input.time, imas.ids_defs.CLOSEST_INTERP
                )
            self.ip = equilibrium.time_slice[0].global_quantities.ip
            self.r0 = equilibrium.vacuum_toroidal_field.r0
            self.b0 = equilibrium.vacuum_toroidal_field.b0[0]

            self.dpressure_dpsi = equilibrium.time_slice[0].profiles_1d.dpressure_dpsi
            self.f_df_dpsi = equilibrium.time_slice[0].profiles_1d.f_df_dpsi
            psi = equilibrium.time_slice[0].profiles_1d.psi
            self.psi_norm = (psi - psi[0]) / (psi[-1] - psi[0])

            self.has_properties = True
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load plasma property outline from {self.input.uri}:"
                f" {str(e)}"
            )
            self.has_properties = False

    @param.depends("input_mode")
    def _panel_property_options(self):
        if self.input_mode == self.MANUAL_INPUT:
            params = pn.Param(self.properties_params, show_name=False)
            params.mapping[param.Number] = FormattedEditableFloatSlider
            params.mapping[param.Integer] = pn.widgets.EditableIntSlider
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            params = pn.Param(self.input, show_name=False)
        return params

    def __panel__(self):
        return self.panel
