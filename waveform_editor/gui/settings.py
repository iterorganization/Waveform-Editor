"""Panel rendering functions for settings objects."""

import panel as pn

from waveform_editor.settings import NiceSettings


def nice_mode_toggle(
    nice_settings: NiceSettings, **kwargs
) -> pn.widgets.RadioButtonGroup:
    """Create a segmented control for switching between NICE modes."""
    widget = pn.widgets.RadioButtonGroup(
        options=[NiceSettings.DIRECT_MODE, NiceSettings.INVERSE_MODE],
        value=nice_settings.mode,
        button_type="default",
        button_style="outline",
        **kwargs,
    )
    widget.link(nice_settings, bidirectional=True, value="mode")
    return widget
