import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path

import imas
import panel as pn
import param
from panel.viewable import Viewer

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


class EquilibriumInput(Viewer):
    """A URI of an equilibrium IDS and one of the times it holds a slice for."""

    uri = param.String(label="URI of the equilibrium IDS")
    time = param.Number(label="Time slice of the input equilibrium IDS")
    times = param.List(default=[], doc="The times the IDS holds a slice for")
    load = param.Event(label="Load")
    reading = param.Boolean(doc="Whether an IDS is being read, which spins this input")

    def __panel__(self):
        return pn.Column(
            pn.pane.HTML("<b>Equilibrium IDS source</b>", margin=(0, 0, 6, 0)),
            pn.Row(
                pn.widgets.TextInput.from_param(
                    self.param.uri,
                    name="IDS URI",
                    placeholder="imas:hdf5?path=...",
                    sizing_mode="stretch_width",
                ),
                pn.widgets.Button(
                    name="Load",
                    button_type="primary",
                    width=80,
                    margin=(28, 0, 0, 0),
                    disabled=self.param.times.rx.not_(),
                    on_click=self._on_load,
                ),
                margin=0,
                align="end",
            ),
            pn.widgets.DiscreteSlider.from_param(
                self.param.time,
                name="Time [s]",
                # A slider needs an option, also when no times have been read yet
                options=self.param.times.rx().rx.or_([0.0]),
                disabled=self.param.times.rx.not_(),
                sizing_mode="stretch_width",
            ),
            css_classes=["property-card", "ids-source-card"],
            stylesheets=[CARD_CSS],
            sizing_mode="stretch_width",
            margin=(0, 10, 8, 0),
            loading=self.param.reading,
        )

    async def _on_load(self, event=None):
        """Load the IDS, for whoever is listening for it."""
        self.reading = True
        # The moment the browser needs to show the spinner before this session is busy
        await asyncio.sleep(0.05)
        self.param.trigger("load")
        self.reading = False

    @param.depends("uri", watch=True)
    async def _read_times(self):
        """Read the times the IDS holds a slice for, so that only those can be
        chosen."""
        self.reading = True
        await asyncio.sleep(0.05)
        self.times = self._ids_times()
        self.reading = False
        if self.times:
            self.time = self.times[0]

    def _ids_times(self):
        """The times of the equilibrium IDS at the URI, empty when it cannot be read.

        Returns:
            List of times.
        """
        if not self.uri:
            return []
        try:
            with imas.DBEntry(self.uri, "r") as entry:
                return entry.get("equilibrium", lazy=True).time.tolist()
        except Exception as e:
            pn.state.notifications.error(f"Could not read {self.uri}: {e}")
            return []


class WarningIndicator(pn.widgets.StaticText):
    def __init__(self, tooltip="", **params):
        params.setdefault("margin", (40, 0, 0, 0))
        icon = (
            f'<span title="{tooltip}" style="cursor:help">⚠️</span>' if tooltip else "⚠️"
        )
        super().__init__(value=icon, **params)
