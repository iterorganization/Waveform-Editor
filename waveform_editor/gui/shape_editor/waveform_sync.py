"""Modal for storing the results of a NICE run in waveforms."""

import pandas as pd
import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.gui.util import STYLES
from waveform_editor.shape_editor.waveform_store import WaveformStore


class WaveformSync(Viewer):
    """Stores the quantities of the last NICE run in waveforms, at a chosen time."""

    export_time = param.Number(doc="The time the values are stored at")
    has_results = param.Boolean(doc="Whether a NICE run has values to store")

    COL_GROUP = "Group"
    COL_NAME = "Waveform"
    COL_VALUE = "Value"
    COL_UNITS = "Units"
    MODAL_WIDTH = 800
    MODAL_HEIGHT = 600

    def __init__(self, main_gui, communicator, **params):
        super().__init__(**params)
        self.main_gui = main_gui
        self.communicator = communicator
        self.store = WaveformStore(main_gui.config)

        self.table = pn.widgets.Tabulator(
            self._frame(),
            show_index=False,
            disabled=True,
            sizing_mode="stretch_both",
            visible=self.param.has_results,
        )
        no_results = pn.pane.Alert(
            "You must run NICE first in order to store the results as waveform",
            alert_type="warning",
            visible=self.param.has_results.rx.not_(),
        )
        self.modal = pn.Modal(
            pn.Column(
                pn.Row(
                    pn.widgets.FloatInput.from_param(self.param.export_time, width=100),
                    pn.widgets.Button(
                        label="Store as waveforms",
                        color="primary",
                        disabled=self.param.has_results.rx.not_(),
                        on_click=self._store,
                        margin=(28, 10, 0, 10),
                    ),
                ),
                self.table,
                no_results,
                sizing_mode="stretch_both",
            ),
            width=self.MODAL_WIDTH,
            height=self.MODAL_HEIGHT,
            stylesheets=STYLES,
            show_close_button=True,
        )
        button_icon = pn.widgets.ButtonIcon(
            icon="table-export",
            description="Store the results as waveforms",
            size="24px",
            margin=(15, 10, 2, 10),
            on_click=lambda event: self._open(),
        )
        self.panel = pn.Row(button_icon, self.modal)

    def _open(self):
        """Show the values of the last run, so they can be stored in waveforms."""
        self.table.value = self._frame()
        self.has_results = not self.table.value.empty
        self.modal.show()

    def _frame(self):
        """The quantities of the last run, as a table."""
        quantities = self.store.get_quantities(
            self.communicator.equilibrium, self.communicator.pf_active
        )
        rows = [
            (group, name, f"{value:.4g}", units)
            for group, name, value, units in quantities
        ]
        return pd.DataFrame(
            rows,
            columns=[self.COL_GROUP, self.COL_NAME, self.COL_VALUE, self.COL_UNITS],
        )

    def _store(self, event=None):
        """Store every quantity of the last run in its waveform."""
        quantities = self.store.get_quantities(
            self.communicator.equilibrium, self.communicator.pf_active
        )
        created = self.store.store(quantities, self.export_time)
        if created:
            self.main_gui.selector.refresh()

        pn.state.notifications.success(
            f"Stored {len(quantities)} values at t={self.export_time} s."
        )
        self.modal.hide()

    def __panel__(self):
        return self.panel
