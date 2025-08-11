import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.util import EquilibriumInput


class PlasmaPropertiesParams(param.Parameterized):
    """Helper class containing parameters defining the plasma properties."""

    ip = param.Number(default=-1.5e7)
    r0 = param.Number(default=6.2)
    b0 = param.Number(default=-5.3)
    alpha = param.Number()
    beta = param.Number()
    gamma = param.Number()


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
            pn.state.notifications.error(
                "Manual plasma properties input is not yet supported"
            )
            self.has_properties = False

    def _load_properties_from_ids(self):
        """Load plasma properties from IDS equilibrium input."""
        if not self.input.uri:
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
            return pn.Param(self.properties_params, show_name=False)
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            return pn.Param(self.input, show_name=False)

    def __panel__(self):
        return self.panel
