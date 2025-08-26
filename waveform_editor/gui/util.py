import panel as pn
import param


class FormattedEditableFloatSlider(pn.widgets.EditableFloatSlider):
    def __init__(self, format="1[.]000", **params):
        super().__init__(format=format, **params)


class EquilibriumInput(param.Parameterized):
    """Parameterized class containing an equilibrium URI and time input."""

    uri = param.String(label="URI of the equilibrium IDS")
    time = param.Number(label="Time slice of the input equilibrium IDS")
