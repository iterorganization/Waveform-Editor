import holoviews as hv
import imas
import numpy as np
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.util import EquilibriumInput, FormattedEditableFloatSlider


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
    dpressure_dpsi_alpha = param.Integer(
        default=2, softbounds=[0, 10], label="dpressure_dpsi alpha"
    )
    dpressure_dpsi_beta = param.Number(
        default=0.6, step=0.01, softbounds=[-10, 10], label="dpressure_dpsi beta"
    )
    dpressure_dpsi_gamma = param.Number(
        default=1.4, softbounds=[0, 10], label="dpressure_dpsi gamma"
    )
    f_df_dpsi_alpha = param.Integer(
        default=2, softbounds=[0, 10], label="f_df_dpsi alpha"
    )
    f_df_dpsi_beta = param.Number(
        default=0.4, softbounds=[-10, 10], label="f_df_dpsi beta"
    )
    f_df_dpsi_gamma = param.Number(
        default=1.4, softbounds=[0, 10], label="f_df_dpsi gamma"
    )


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

    profile_overlay = param.Parameter(
        default=hv.Overlay([hv.Curve([])]),
        doc="Holoviews overlay of the p' and ff' profiles",
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

    @param.depends("properties_params.param", "input.param", "input_mode", watch=True)
    def _load_plasma_properties(self):
        """Update plasma properties based on input mode."""
        if self.input_mode == self.EQUILIBRIUM_INPUT:
            self._load_properties_from_ids()
        elif self.input_mode == self.MANUAL_INPUT:
            self._load_properties_from_params()

        if self.has_properties:
            p_prime_curve = hv.Curve(
                (self.psi, self.dpressure_dpsi), kdims="Poloidal flux", label="p'"
            )
            ff_prime_curve = hv.Curve(
                (self.psi, self.f_df_dpsi), kdims="Poloidal flux", label="ff'"
            )

            self.profile_overlay = (p_prime_curve * ff_prime_curve).opts(
                hv.opts.Overlay(title="Plasma Profiles")
            )
        else:
            self.profile_overlay = hv.Overlay([hv.Curve([])])

    def _load_properties_from_params(self):
        self.ip = self.properties_params.ip
        self.r0 = self.properties_params.r0
        self.b0 = self.properties_params.b0
        self.psi = np.linspace(-1, 0, 200)
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
        base = 1.0 - np.power(psi, alpha)
        profile = beta * np.power(base, gamma)
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
            params = pn.GridBox(*params, ncols=3)
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            params = pn.Param(self.input, show_name=False)

        return params

    def __panel__(self):
        return self.panel
