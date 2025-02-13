import holoviews as hv
import panel as pn

from waveform_editor.yaml_parser import YamlParser

hv.extension("plotly")

# TODO: Current UI implementation is only for testing purposes. In this future this is
# to be rewritten in a proper class-based form.
# The gui can be launched using:
# panel serve waveform_editor/waveform_editor_gui.py --dev --show

code_editor = pn.widgets.CodeEditor(
    value="""\
waveform:
- {type: linear, from: 0, to: 8, duration: 5}
- {type: sine-wave, base: 8, amplitude: 2, frequency: 1, duration: 4}
- {type: constant, value: 8, duration: 3}
- {type: smooth, from: 8, to: 0, duration: 2}
""",
    width=600,
    height=1200,
    theme="tomorrow",
    language="yaml",
)

yaml_parser = YamlParser()

yaml_alert = pn.pane.Alert(
    "### The YAML did not parse correctly! (see editor)",
    alert_type="danger",
    visible=False,
)
error_alert = pn.pane.Alert(
    "### There was an error in the YAML configuration (see editor).",
    alert_type="warning",
    visible=False,
)


def update_plot(value):
    yaml_alert.visible = error_alert.visible = False
    yaml_parser.parse_waveforms(value)

    code_editor.annotations = list(yaml_parser.waveform.annotations)
    code_editor.param.trigger("annotations")

    # Show alert when there is a yaml parsing error
    if yaml_parser.has_yaml_error:
        yaml_alert.visible = True
    elif code_editor.annotations:
        error_alert.visible = True
    return yaml_parser.plot_tendencies()


plot = hv.DynamicMap(pn.bind(update_plot, value=code_editor.param.value))
plot_and_alert = pn.Column(plot, yaml_alert, error_alert)
layout = pn.Row(code_editor, plot_and_alert)
layout.servable()
