import holoviews as hv
import panel as pn
import param
import yaml

from waveform_editor.yaml_parser import YamlParser

hv.extension("plotly")

# Load YAML data
yaml_parser = YamlParser()
yaml_file = "waveform_editor/test.yaml"

with open(yaml_file) as f:
    yaml_data = yaml.safe_load(f)


class WaveformPlot(param.Parameterized):
    """Class to handle dynamic waveform plotting."""

    selected_keys = param.ListSelector(default=[], objects=[])

    def update_plot(self, selected_keys):
        """Update plot when a waveform key is selected using YamlParser."""

        if not selected_keys:
            return hv.Overlay([hv.Curve([])]).opts(title="Select a waveform")

        key = selected_keys[0]
        value = self.get_yaml_value(yaml_data, key)

        if value is None:
            return hv.Overlay([hv.Curve([])])

        yaml_string = yaml.dump({key: value})

        yaml_parser.parse_waveforms(yaml_string)

        plot = yaml_parser.plot_tendencies()
        if not isinstance(plot, hv.Overlay):
            plot = hv.Overlay([plot])

        return plot

    def get_yaml_value(self, yaml_dict, key):
        """
        Recursively search for the value associated with a key in a nested YAML dictionary.

        :param yaml_dict: Parsed YAML dictionary
        :param key: Key to find in the dictionary
        :return: Corresponding value or None if not found
        """
        if isinstance(yaml_dict, dict):
            for k, v in yaml_dict.items():
                if k == key:
                    return v  # Found the exact key, return its value
                elif isinstance(v, dict):  # Recursive search in nested dictionaries
                    result = self.get_yaml_value(v, key)
                    if result is not None:
                        return result
        return None


waveform_plot = WaveformPlot()

plot = hv.DynamicMap(
    waveform_plot.update_plot, streams=[waveform_plot.param.selected_keys]
)


def create_ui(data):
    """Recursively create a Panel UI structure from the YAML"""
    categories = []
    options = []

    for key, value in data.items():
        if key == "globals":
            continue
        elif "/" in key:
            # If it contains '/', treat it as an option for selection
            options.append(key)
        else:
            categories.append((key, create_ui(value)))

    content = []
    if options:
        check_buttons = pn.widgets.CheckButtonGroup(
            value=[],
            options=options,
            button_style="outline",
            button_type="primary",
            sizing_mode="stretch_width",
            orientation="vertical",
            stylesheets=["button {text-align: left!important;}"],
        )

        # Link button selection to waveform plot update
        def on_select(event):
            waveform_plot.selected_keys = event.new  # Update parameter

        check_buttons.param.watch(on_select, "value")
        content.append(check_buttons)

    if categories:
        accordion = pn.Accordion(*categories)
        content.append(accordion)

    return pn.Column(*content, sizing_mode="stretch_width")


yaml_ui = create_ui(yaml_data)

pn.template.MaterialTemplate(
    title="Waveform Editor (v0.0 ~ mockup)",
    sidebar=[yaml_ui],
    main=pn.Column(pn.pane.Markdown("## Dynamic YAML Viewer"), plot),
).servable()
