import holoviews as hv
import imas
import numpy as np
import panel as pn
import param
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
    dpressure_dpsi_alpha = param.Integer(default=2, softbounds=[0, 10], label="Alpha")
    dpressure_dpsi_beta = param.Number(
        default=0.6, step=0.01, softbounds=[-10, 10], label="Beta"
    )
    dpressure_dpsi_gamma = param.Number(default=1.4, softbounds=[0, 10], label="Gamma")
    f_df_dpsi_alpha = param.Integer(default=2, softbounds=[0, 10], label="Alpha")
    f_df_dpsi_beta = param.Number(default=0.4, softbounds=[-10, 10], label="Beta")
    f_df_dpsi_gamma = param.Number(default=1.4, softbounds=[0, 10], label="Gamma")


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
        self.psi = None
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
        self.psi = np.linspace(0, 1, 200)
        self.dpressure_dpsi = self._calculate_parametric_profile(
            self.psi,
            self.properties_params.dpressure_dpsi_alpha,
            self.properties_params.dpressure_dpsi_beta,
            self.properties_params.dpressure_dpsi_gamma,
        )
        self.f_df_dpsi = self._calculate_parametric_profile(
            self.psi,
            self.properties_params.f_df_dpsi_alpha,
            self.properties_params.f_df_dpsi_beta,
            self.properties_params.f_df_dpsi_gamma,
        )
        self.has_properties = True

    def _calculate_parametric_profile(self, psi, alpha, beta, gamma):
        """Compute parameterized profiles for dpressure_dpsi and f_df_dpsi.

        Adapted from NICE, by Blaise Faugeras:
        https://gitlab.inria.fr/blfauger/nice

        Args:
            psi: Normalized poloidal flux.
            alpha: Exponent controlling profile steepness near ψ = 0.
            beta: Scaling coefficient for the profile amplitude.
            gamma: Exponent controlling the shape near ψ = 1.

        returns:
            ndarray for the evaluated profile for each psi.
        """
        base = 1.0 - np.power(psi, alpha)
        profile = -1 * beta * np.power(base, gamma)
        return profile

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
            self.psi = equilibrium.time_slice[0].profiles_1d.psi
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

            return pn.Column(
                *params[0:3],
                pn.pane.Markdown("#### dpressure_dpsi Parameterization", margin=0),
                *params[3:6],
                pn.pane.Markdown("#### f_df_dpsi Parameterization", margin=0),
                *params[6:9],
                margin=(5, 10),
            )
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            return pn.Param(self.input, show_name=False)

    def __panel__(self):
        return self.panel
