import imas
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.shape_editor.plasma_shape import EquilibriumInput


class PlasmaPropertiesParams(param.Parameterized):
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
    has_properties = param.Boolean(doc="Whether a plasma shape is loaded.")

    def __init__(self, equilibrium):
        super().__init__()
        self.equilibrium = equilibrium
        self.radio_box = pn.widgets.RadioBoxGroup.from_param(
            self.param.input_mode, inline=True, margin=20
        )

    @param.depends("properties_params.param", "input.param", "input_mode", watch=True)
    def _load_plasma_properties(self):
        if self.input_mode == self.EQUILIBRIUM_INPUT:
            self._load_properties_from_ids()
        elif self.input_mode == self.MANUAL_INPUT:
            pn.state.notifications.error(
                "Manual plasma properties input is not yet supported"
            )
            self.has_properties = False

    def _load_properties_from_ids(self):
        if not self.input.equilibrium:
            return
        try:
            with imas.DBEntry(self.input.equilibrium, "r") as entry:
                equilibrium = entry.get_slice(
                    "equilibrium", self.input.time, imas.ids_defs.CLOSEST_INTERP
                )

            self.equilibrium.time_slice[
                0
            ].global_quantities.ip = equilibrium.time_slice[0].global_quantities.ip

            self.equilibrium.vacuum_toroidal_field.r0 = (
                equilibrium.vacuum_toroidal_field.r0
            )
            self.equilibrium.vacuum_toroidal_field.b0[0] = (
                equilibrium.vacuum_toroidal_field.b0[0]
            )
            profiles_1d = equilibrium.time_slice[0].profiles_1d
            self.equilibrium.time_slice[
                0
            ].profiles_1d.dpressure_dpsi = profiles_1d.dpressure_dpsi
            self.equilibrium.time_slice[0].profiles_1d.f_df_dpsi = profiles_1d.f_df_dpsi
            self.equilibrium.time_slice[0].profiles_1d.psi = profiles_1d.psi
            self.has_properties = True
        except Exception as e:
            pn.state.notifications.error(
                f"Could not load plasma property outline from {self.input.equilibrium}:"
                f" {str(e)}"
            )
            self.has_properties = False

    @param.depends("input_mode")
    def _panel_shape_options(self):
        if self.input_mode == self.MANUAL_INPUT:
            parameters = pn.Column(
                self.radio_box, pn.Param(self.properties_params, show_name=False)
            )
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            parameters = pn.Column(
                self.radio_box, pn.Param(self.input, show_name=False)
            )
        return parameters

    def __panel__(self):
        return self._panel_shape_options
