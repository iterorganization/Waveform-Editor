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


def update_plot(value):
    yaml_parser.parse_waveforms_from_string(value)

    code_editor.annotations = yaml_parser.annotations
    code_editor.param.trigger("annotations")

    if yaml_parser.waveform is None:
        return yaml_parser.plot_empty()
    else:
        return yaml_parser.plot_tendencies()


hv_dynamic_map = hv.DynamicMap(pn.bind(update_plot, value=code_editor.param.value))
layout = pn.Row(code_editor, hv_dynamic_map)
layout.servable()
