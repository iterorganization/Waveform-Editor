import panel as pn
import param
from panel.viewable import Viewer


class ShapeParams(Viewer):
    """Parameters related to plasma shape"""

    PARAMETERIZED_INPUT = "Parameterized"
    EQUILIBRIUM_INPUT = "Equilibrium IDS"
    input_mode = param.ObjectSelector(
        default=EQUILIBRIUM_INPUT,
        objects=[EQUILIBRIUM_INPUT, PARAMETERIZED_INPUT],
        label="Shape input mode",
    )

    equilibrium_input = param.String(label="Input 'equilibrium' IDS")
    time_input = param.Number(label="Time for input equilibrium")

    parametric_bnd = param.Boolean(label="Use parameterized boundary")
    a = param.Number(default=1.9, bounds=[1, 2], label="a")
    center_r = param.Number(default=6.2, bounds=[5, 7], label="center_r")
    center_z = param.Number(default=0.545, bounds=[0, 1.5], label="center_z")
    kappa = param.Number(default=1.8, bounds=[0, 3], label="kappa")
    delta = param.Number(default=0.43, bounds=[-1, 1], label="delta")
    rx = param.Number(default=5.089, bounds=[4.5, 6], label="rx")
    zx = param.Number(default=-3.346, bounds=[-4, -2], label="zx")
    n_desired_bnd_points = param.Integer(
        default=96, bounds=[1, 200], label="n_desired_bnd_points"
    )

    @param.depends("input_mode")
    def _dynamic_panel(self):
        widgets = {
            "input_mode": {"widget_type": pn.widgets.RadioBoxGroup, "inline": True}
        }
        if self.input_mode == self.PARAMETERIZED_INPUT:
            self.parametric_bnd = True
            parameters = pn.Param(
                self,
                parameters=[
                    "input_mode",
                    "a",
                    "center_r",
                    "center_z",
                    "kappa",
                    "delta",
                    "rx",
                    "zx",
                    "n_desired_bnd_points",
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
