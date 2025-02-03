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
- {type: constant, value: 8, duration: 3}
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


def update_plot(value):
    yaml_parser.tendencies = []
    yaml_parser.parse_waveforms_from_string(value)

    return yaml_parser.plot_tendencies(True)


hv_dynamic_map = hv.DynamicMap(pn.bind(update_plot, value=code_editor.param.value))
layout = pn.Row(code_editor, hv_dynamic_map)
layout.servable()
