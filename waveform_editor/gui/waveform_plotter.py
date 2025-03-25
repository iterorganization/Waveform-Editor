import holoviews as hv
import param
import yaml

from waveform_editor.yaml_parser import YamlParser


class WaveformPlotter(param.Parameterized):
    """Class to handle dynamic waveform plotting."""

    selected_keys = param.ListSelector(default=[], objects=[])

    def __init__(self, yaml_data, **params):
        super().__init__(**params)
        self.yaml_data = yaml_data

    def plot_tendencies(self, waveform, label, plot_time_points=False):
        """
        Plot the tendencies and return the curve.

        Args:
            plot_time_points (bool): Whether to include markers for the data points.

        Returns:
            A Holoviews Curve object.
        """
        times, values = waveform.get_value()

        # Prevent updating the plot if there are no tendencies, for example when a
        # YAML error is encountered
        if not waveform.tendencies:
            return hv.Curve([])

        # TODO: The y axis should show the units of the plotted waveform
        line = hv.Curve((times, values), "Time (s)", "Value", label=label).opts(
            line_width=2, framewise=True, show_legend=True
        )

        if plot_time_points:
            points = hv.Scatter((times, values), "Time (s)", "Value").opts(
                size=5,
                color="red",
                marker="circle",
            )
            return line * points

        return line

    def update_plot(self, selected_keys, width=1200, height=600):
        """Update plot when waveform keys are selected using YamlParser."""
        yaml_parser = YamlParser()
        empty_overlay = hv.Overlay([hv.Curve([])]).opts(
            title="",
            show_legend=True,
            width=width,
            height=height,
        )

        if not selected_keys:
            return empty_overlay
        curves = []

        for key in selected_keys:
            value = self.get_yaml_value(self.yaml_data, key)

            if value is None:
                continue

            # TODO: Dont dump back to yaml
            yaml_string = yaml.dump({key: value})

            waveform = yaml_parser.parse_waveforms(yaml_string)
            plot = self.plot_tendencies(waveform, key)

            curves.append(plot)

        # Combine all curve objects into a single overlay
        if curves:
            combined_overlay = hv.Overlay(curves)
            return combined_overlay.opts(
                title="",
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

    def get_dynamic_map(self):
        return hv.DynamicMap(
            self.update_plot,
            streams=[self.param.selected_keys],
        )
