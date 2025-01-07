import panel as pn

from waveform_editor.yaml_parser import YamlParser

code_editor = pn.widgets.CodeEditor(
    value="""\
waveform:
- {type: constant, value: 5, duration: 3}
- {type: linear, duration: 5}
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

initial_yaml = code_editor.value
yaml_parser.parse_waveforms(initial_yaml)
initial_fig = yaml_parser.plot_tendencies()
plotly_pane = pn.pane.Plotly(initial_fig)


def update_plot(event):
    yaml_parser.tendencies = []
    yaml_content = code_editor.value
    yaml_parser.parse_waveforms(yaml_content)

    for tendency in yaml_parser.tendencies:
        tendency.param.trigger("prev_tendency")
        tendency.param.trigger("next_tendency")

    fig = yaml_parser.plot_tendencies()
    plotly_pane.object = fig
    print("updated")


code_editor.param.watch(update_plot, "value")

layout = pn.Row(code_editor, plotly_pane)

layout.servable()
