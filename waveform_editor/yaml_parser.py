import holoviews as hv
import yaml

from waveform_editor.waveform import Waveform


class YamlParser:
    def parse_waveforms_from_file(self, file_path):
        """Loads a YAML file from a file path and stores its tendencies into a list.

        Args:
            file_path: File path of the YAML file.
        """
        with open(file_path) as file:
            waveform_yaml = yaml.load(file, yaml.SafeLoader)
        self.waveform = Waveform(waveform_yaml)

    def parse_waveforms_from_string(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        waveform_yaml = yaml.load(yaml_str, yaml.SafeLoader)
        waveform = waveform_yaml.get("waveform", [])
        self.waveform = Waveform(waveform)

    def plot_tendencies(self, plot_time_points=False):
        """
        Plot the tendencies in a Holoviews Overlay and return this Overlay.

        Args:
            plot_time_points (bool): Whether to include markers for the data points.

        Returns:
            A Holoviews Overlay object.
        """
        times, values = self.waveform.generate()

        overlay = hv.Overlay()

        # By merging all the tendencies into a single holoviews curve, we circumvent
        # an issue that occurs when returning an overlay of multiple curves, where
        # tendencies of previous inputs are sometimes not cleared correctly.
        line = hv.Curve((times, values), "Time (s)", "Value").opts(
            line_width=2, color="blue"
        )
        overlay *= line
        if plot_time_points:
            points = hv.Scatter((times, values), "Time (s)", "Value").opts(
                size=5,
                color="red",
                marker="circle",
            )
            overlay *= points

        return overlay.opts(title="Waveform", width=800, height=400)
