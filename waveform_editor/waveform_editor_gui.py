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


class WaveformPlotter(param.Parameterized):
    """Class to handle dynamic waveform plotting."""

    selected_keys = param.ListSelector(default=[], objects=[])

    def update_plot(self, selected_keys, width=1200, height=600):
        """Update plot when waveform keys are selected using YamlParser."""
        empty_overlay = hv.Overlay([hv.Curve([])]).opts(
            title="Select a waveform to view",
            show_legend=True,
            width=width,
            height=height,
        )

        if not selected_keys:
            return empty_overlay
        curves = []

        for key in selected_keys:
            value = self.get_yaml_value(yaml_data, key)

            if value is None:
                continue

            yaml_string = yaml.dump({key: value})

            yaml_parser.parse_waveforms(yaml_string)
            plot = yaml_parser.plot_tendencies(key)

            curves.append(plot)

        # Combine all curve objects into a single overlay
        if curves:
            combined_overlay = hv.Overlay(curves)
            return combined_overlay.opts(
                title="Selected Waveforms",
                show_legend=True,
                width=width,
                height=height,
            )

        return empty_overlay

    def get_yaml_value(self, yaml_dict, key):
        if isinstance(yaml_dict, dict):
            for k, v in yaml_dict.items():
                if k == key:
                    return v  # Found the exact key, return its value
                elif isinstance(v, dict):  # Recursive search in nested dictionaries
                    result = self.get_yaml_value(v, key)
                    if result is not None:
                        return result
        return None


def create_waveform_selector(data):
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
            categories.append((key, create_waveform_selector(value)))

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
            waveform_plotter.selected_keys = event.new

        check_buttons.param.watch(on_select, "value")
        content.append(check_buttons)

    if categories:
        accordion = pn.Accordion(*categories)
        content.append(accordion)

    return pn.Column(*content, sizing_mode="stretch_width")


waveform_plotter = WaveformPlotter()

waveform_plot = hv.DynamicMap(
    waveform_plotter.update_plot, streams=[waveform_plotter.param.selected_keys]
)
waveform_selector = create_waveform_selector(yaml_data)

pn.template.MaterialTemplate(
    title="Waveform Editor (Draft version)",
    sidebar=[waveform_selector],
    main=pn.Column(pn.pane.Markdown("# Waveform Inspector"), waveform_plot),
).servable()
