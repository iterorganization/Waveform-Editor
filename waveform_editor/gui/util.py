import asyncio
from pathlib import Path

import imas
import panel as pn
import param
from panel.viewable import Viewer

STYLES = [(Path(__file__).parent / "styles" / "styles.css").read_text()]
CARD_CSS = (Path(__file__).parent / "styles" / "property_card.css").read_text()


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
    step = param.Number(default=0.01, doc="A step of about one slice for the input")
    typed_time = param.Number(
        default=0.0, allow_None=True, doc="A time typed in, snapped to a slice"
    )

    def __panel__(self):
        return pn.Column(
            pn.pane.HTML("<b>Equilibrium IDS source</b>", margin=(0, 0, 6, 0)),
            pn.widgets.TextInput.from_param(
                self.param.uri,
                name="IDS URI",
                placeholder="imas:hdf5?path=...",
                sizing_mode="stretch_width",
            ),
            pn.Row(
                pn.widgets.FloatInput.from_param(
                    self.param.typed_time,
                    name="Time [s]",
                    description="Select a specific time slice to load",
                    width=90,
                    step=self.param.step,
                    format="0[.]000",
                    margin=(0, 20, 10, 0),
                ),
                pn.widgets.DiscreteSlider.from_param(
                    self.param.time,
                    name="",
                    options=self.param.times.rx().rx.or_([0.0]),
                    show_value=False,
                    sizing_mode="stretch_width",
                    align="end",
                    margin=(0, 0, 14, 0),
                ),
                pn.widgets.Button(
                    name="Load",
                    button_type="primary",
                    width=80,
                    align="end",
                    margin=(0, 0, 10, 10),
                    on_click=self._on_load,
                ),
                margin=0,
                visible=self.param.times.rx.bool(),
            ),
            css_classes=["property-card", "ids-source-card"],
            stylesheets=[CARD_CSS],
            sizing_mode="stretch_width",
            margin=(0, 10, 8, 0),
            loading=self.param.reading,
        )

    @param.depends("typed_time", watch=True)
    def _snap_typed_time(self):
        """Take the slice closest to a typed time, since only the times the IDS holds
        a slice for can be chosen."""
        if self.times and self.typed_time is not None:
            self.time = min(self.times, key=lambda time: abs(time - self.typed_time))
            # Show the snapped time, also when it leaves the typed time behind
            self.typed_time = self.time

    @param.depends("time", watch=True)
    def _show_time(self):
        """Show the time of the slice in use, also when the slider set it."""
        self.typed_time = self.time

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
        if len(self.times) > 1:
            self.step = (self.times[-1] - self.times[0]) / (len(self.times) - 1)
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
