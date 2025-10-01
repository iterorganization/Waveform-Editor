import panel as pn
import param


class FormattedEditableFloatSlider(pn.widgets.EditableFloatSlider):
    def __init__(self, format="1[.]000", width=450, **params):
        super().__init__(format=format, width=width, **params)


class FixedWidthEditableIntSlider(pn.widgets.EditableIntSlider):
    def __init__(self, width=450, **params):
        super().__init__(width=width, **params)


class EquilibriumInput(param.Parameterized):
    """Parameterized class containing an equilibrium URI and time input."""

    uri = param.String(label="URI of the equilibrium IDS")
    time = param.Number(label="Time slice of the input equilibrium IDS")


class WarningIndicator(pn.widgets.StaticText):
    def __init__(self, **params):
        super().__init__(value="⚠️", margin=(40, 0, 0, 0), **params)
