"""Panel-aware NICE integration: adds a Terminal widget for displaying NICE output."""

import panel as pn

from waveform_editor.shape_editor.nice_integration import (
    NiceIntegration as _NiceIntegration,
)
from waveform_editor.shape_editor.nice_integration import (
    OutputCommunicatorProtocol,
)


class NiceIntegration(_NiceIntegration):
    """NiceIntegration with a Panel Terminal widget for displaying NICE output."""

    def __init__(self, imas_factory):
        self.terminal = pn.widgets.Terminal(
            # write_to_console=True,
            sizing_mode="stretch_width",
            options={"scrollback": 10000, "wrap": True},
            height=200,
            max_width=750,
        )
        super().__init__(imas_factory, on_output=self.terminal.write)

    def create_communicator_protocol(self):
        return TerminalCommunicatorProtocol(self.terminal)


class TerminalCommunicatorProtocol(OutputCommunicatorProtocol):
    """Displays subprocess output in a Panel Terminal widget."""

    def __init__(self, terminal):
        super().__init__(terminal.write)
