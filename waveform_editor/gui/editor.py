import textwrap
from typing import Optional

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.derived_waveform import DerivedWaveform
from waveform_editor.waveform import Waveform


class WaveformEditor(Viewer):
    """A Panel interface for waveform editing."""

    waveform = param.ClassSelector(
        class_=(Waveform, DerivedWaveform),
        doc="Waveform currently being edited. Use `set_waveform` to change.",
    )
    stored_string = param.String(
        default=None,
        doc="Contains the waveform text before any changes were made in the editor.",
    )
    error_message = param.String(doc="Error or warning message to show in alert.")
    alert_type = param.String(default="danger")
    has_changed = param.Boolean(
        allow_refs=True, doc="Whether there are unsaved changes in the editor."
    )

    def __init__(self, config):
        super().__init__()
        self.config = config

        has_error = self.param.error_message.rx.bool()

        self.error_alert = pn.pane.Alert(
            object=self.param.error_message,
            alert_type=self.param.alert_type,
            visible=has_error,
        )

        self.code_editor = pn.widgets.CodeEditor(
            sizing_mode="stretch_both",
            language="yaml",
            readonly=self.param.waveform.rx.is_(None),
        )
        self.code_editor.param.watch(self.on_value_change, "value")

        self.has_changed = self.param.stored_string.rx.bool() & (
            self.code_editor.param.value.rx() != self.param.stored_string.rx()
        )
        self.layout = pn.Column(self.code_editor, self.error_alert)

        # Initialize empty
        self.set_waveform(None)

    def set_waveform(self, waveform: Optional[str]) -> None:
        """Start editing a waveform.

        Args:
            waveform: Name of the waveform to edit. Can be set to None to disable the
                editor.
        """
        self.waveform = None if waveform is None else self.config[waveform]
        self.error_message = ""
        if self.waveform is None:
            self.code_editor.value = "Select a waveform to edit"
            self.stored_string = None
        else:
            waveform_yaml = self.waveform.get_yaml_string()
            self.stored_string = self.code_editor.value = waveform_yaml

    def on_value_change(self, event):
        """Update the plot based on the YAML editor input.

        Args:
            event: Event containing the code editor value input.
        """
        if self.waveform is None:
            return

        # Parse waveform YAML
        editor_text = event.new
        name = self.waveform.name
        # Merge code editor string with name into a single YAML string, ensure that
        # dashed lists are placed below the key containing the waveform name
        if editor_text.lstrip().startswith("- "):
            waveform_yaml = f"{name}:\n{editor_text}"
        # Derived waveforms are parsed as YAML block strings
        elif "'" in editor_text or '"' in editor_text:
            indented_text = textwrap.indent(editor_text, "  ")
            waveform_yaml = f"{name}: |\n{indented_text}"
        else:
            waveform_yaml = f"{name}: {editor_text}"
        waveform = self.config.parse_waveform(waveform_yaml)
        self.handle_exceptions(waveform)
        if not self.error_message:
            self.waveform = waveform
            self.save_waveform()

    def handle_exceptions(self, waveform):
        annotations = waveform.annotations
        self.code_editor.annotations = list(annotations)
        if self.config.parser.parse_errors:  # Handle errors
            self.error_message = (
                "### The YAML did not parse correctly\n  "
                + f"{self.config.parser.parse_errors[0]}"
            )
            self.alert_type = "danger"
        elif annotations:
            self.error_message = (
                "### There was an error in the YAML configuration\n" + f"{annotations}"
            )
            self.alert_type = "warning"
        else:
            if isinstance(waveform, DerivedWaveform):
                try:
                    self.config.check_safe_to_replace(waveform)
                except Exception as e:
                    self.error_message = f"### {str(e)}"
                    self.alert_type = "danger"
                    return
            self.error_message = ""  # Clear any previous errors or warnings

    def save_waveform(self):
        """Store the waveform into the WaveformConfiguration."""
        self.config.replace_waveform(self.waveform)
        self.stored_string = self.code_editor.value

    def __panel__(self):
        """Return the editor panel UI."""
        return self.layout
