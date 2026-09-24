import xml.etree.ElementTree as ET
from pathlib import Path

import panel as pn
import param

STYLES = [(Path(__file__).parent / "styles" / "styles.css").read_text()]
CARD_CSS = (Path(__file__).parent / "styles" / "property_card.css").read_text()


def set_xml_parameter(xml_params, name, value):
    """Set a NICE parameter, adding it if it is not in the parameter file."

    Args:
        xml_params: XML representing configuration parameters, updated in-place.
        name: Name of the parameter.
        value: Value to set it to.
    """
    parameter = xml_params.find(name)
    if parameter is None:
        parameter = ET.SubElement(xml_params, name)
    parameter.text = str(value)


def _resolve_width(width, stretch_width, params):
    if stretch_width:
        params.setdefault("sizing_mode", "stretch_width")
        return None
    return width


class FormattedEditableFloatSlider(pn.widgets.EditableFloatSlider):
    def __init__(self, format="1[.]000", width=450, stretch_width=False, **params):
        width = _resolve_width(width, stretch_width, params)
        super().__init__(format=format, width=width, **params)


class FixedWidthEditableIntSlider(pn.widgets.EditableIntSlider):
    def __init__(self, width=450, stretch_width=False, **params):
        width = _resolve_width(width, stretch_width, params)
        super().__init__(width=width, **params)


class EquilibriumInput(param.Parameterized):
    """Parameterized class containing an equilibrium URI and time input."""

    uri = param.String(label="URI of the equilibrium IDS")
    time = param.Number(label="Time slice of the input equilibrium IDS")


class WarningIndicator(pn.widgets.StaticText):
    def __init__(self, tooltip="", **params):
        params.setdefault("margin", (40, 0, 0, 0))
        icon = (
            f'<span title="{tooltip}" style="cursor:help">⚠️</span>' if tooltip else "⚠️"
        )
        super().__init__(value=icon, **params)
