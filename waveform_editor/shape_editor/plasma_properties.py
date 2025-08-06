import panel as pn
import param
from panel.viewable import Viewer


class PlasmaProperties(Viewer):
    MANUAL_INPUT = "Manual"
    EQUILIBRIUM_INPUT = "Equilibrium IDS"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, MANUAL_INPUT],
        label="Plasma properties input mode",
    )

    equilibrium_input = param.String(label="Input 'equilibrium' IDS")
    time_input = param.Number(label="Time for input equilibrium")

    ip = param.Number(default=-1.5e7)
    r0 = param.Number(default=6.2)
    b0 = param.Number(default=-5.3)
    alpha = param.Number()
    beta = param.Number()
    gamma = param.Number()

    @param.depends("input_mode")
    def _dynamic_panel(self):
        widgets = {
            "input_mode": {"widget_type": pn.widgets.RadioBoxGroup, "inline": True}
        }
        if self.input_mode == self.MANUAL_INPUT:
            self.parametric_bnd = True
            parameters = pn.Param(
                self,
                parameters=[
                    "input_mode",
                    "ip",
                    "r0",
                    "alpha",
                    "beta",
                    "gamma",
                ],
                widgets=widgets,
                show_name=False,
            )
        elif self.input_mode == self.EQUILIBRIUM_INPUT:
            self.parametric_bnd = False
            parameters = pn.Param(
                self,
                parameters=[
                    "input_mode",
                    "equilibrium_input",
                    "time_input",
                ],
                widgets=widgets,
                show_name=False,
            )

        return parameters

    def __panel__(self):
        return pn.Column(self._dynamic_panel)
