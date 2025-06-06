from typing import Optional

import panel as pn
import param
from panel.viewable import Viewer

from waveform_editor.waveform import Waveform


class WaveformEditor(Viewer):
    """A Panel interface for waveform editing."""

    waveform = param.ClassSelector(
        class_=Waveform,
        doc="Waveform currently being edited. Use `set_waveform` to change.",
    )

    def __init__(self, config):
        super().__init__()
        self.config = config
        # Contains the waveform text before any changes were made in the editor
        self.stored_string = None

        # Code editor UI
        self.error_alert = pn.pane.Alert()
        # Show error alert when object is set:
        self.error_alert.visible = self.error_alert.param.object.rx.bool()

        self.code_editor = pn.widgets.CodeEditor(
            sizing_mode="stretch_both",
            language="yaml",
            readonly=self.param.waveform.rx.is_(None),
        )
        self.code_editor.param.watch(self.on_value_change, "value")

        save_button = pn.widgets.ButtonIcon(
            icon="device-floppy",
            size="30px",
            active_icon="check",
            description="Save waveform",
            on_click=self.save_waveform,
        )
        self.layout = pn.Column(save_button, self.code_editor, self.error_alert)

        # Initialize empty
        self.set_waveform(None)

    def set_waveform(self, waveform: Optional[str]) -> None:
        """Start editing a waveform.

        Args:
            waveform: Name of the waveform to edit. Can be set to None to disable the
                editor.
        """
        self.waveform = None if waveform is None else self.config[waveform]
        self.error_alert.object = ""  # clear any errors
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
        else:
            waveform_yaml = f"{name}: {editor_text}"
        waveform = self.config.parse_waveform(waveform_yaml)

        # Handle exceptions:
        annotations = waveform.annotations
        self.code_editor.annotations = list(annotations)
        if self.config.parser.parse_errors:  # Handle errors
            self.error_alert.object = (
                "### The YAML did not parse correctly\n  "
                f"{self.config.parser.parse_errors[0]}"
            )
            self.error_alert.alert_type = "danger"
        else:  # No errors
            if self.code_editor.annotations:  # Handle warnings
                self.error_alert.object = (
                    f"### There was an error in the YAML configuration\n{annotations}"
                )
                self.error_alert.alert_type = "warning"
            else:
                self.error_alert.object = ""  # Clear any previous errors or warnings
            # There are no errors: update self.waveform
            self.waveform = waveform

    def save_waveform(self, event=None):
        """Store the waveform into the WaveformConfiguration."""
        if self.error_alert.visible:
            pn.state.notifications.error("Cannot save YAML with errors.")
            return

        self.config.replace_waveform(self.waveform)
        self.stored_string = self.code_editor.value
        pn.state.notifications.success("Succesfully saved waveform!")

    def has_changed(self):
        """Return whether the code editor value was changed from its stored value"""
        return self.stored_string and self.code_editor.value != self.stored_string

    def __panel__(self):
        """Return the editor panel UI."""
        return self.layout
