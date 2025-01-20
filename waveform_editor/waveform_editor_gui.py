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
    annotations=[
        dict(row=1, column=0, text="an error", type="error"),
        dict(row=2, column=0, text="a warning", type="warning"),
    ],
)

yaml_parser = YamlParser()

initial_yaml_str = code_editor.value
yaml_parser.parse_waveforms_from_string(initial_yaml_str)
initial_plot = yaml_parser.plot_tendencies()
hvplot_pane = pn.pane.HoloViews(initial_plot)


def update_plot(event):
    yaml_parser.tendencies = []
    yaml_str = code_editor.value
    yaml_parser.parse_waveforms_from_string(yaml_str)

    updated_plot = yaml_parser.plot_tendencies()
    hvplot_pane.object = updated_plot


code_editor.param.watch(update_plot, "value")

layout = pn.Row(code_editor, hvplot_pane)

layout.servable()
