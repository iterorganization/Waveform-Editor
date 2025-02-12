import holoviews as hv
import yaml

from waveform_editor.waveform import Waveform


class LineNumberYamlLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        # The line numbers must be extracted to be able to display the error messages
        mapping = super().construct_mapping(node, deep)
        mapping["line_number"] = node.start_mark.line
        return mapping


class YamlParser:
    def __init__(self):
        self.waveform = Waveform()

    def parse_waveforms_from_file(self, file_path):
        """Loads a YAML file from a file path and stores its tendencies into a list.

        Args:
            file_path: File path of the YAML file.
        """
        with open(file_path) as file:
            self.parse_waveforms_from_string(file)

    def parse_waveforms_from_string(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        self.has_yaml_error = False
        try:
            waveform_yaml = yaml.load(yaml_str, Loader=LineNumberYamlLoader)
            waveform = waveform_yaml.get("waveform", [])
            self.waveform = Waveform(waveform=waveform)
        except yaml.YAMLError as e:
            self._handle_yaml_error(e)

    def _handle_yaml_error(self, error):
        """Handles YAML parsing errors by adding it to the annotations of the waveform.

        Args:
            error: The YAML error to add to the annotations.
        """
        self.waveform.annotations.clear()
        self.waveform.annotations.add_yaml_error(error)
        self.waveform.tendencies = []
        self.has_yaml_error = True

    def plot_tendencies(self, plot_time_points=False):
        """
        Plot the tendencies in a Holoviews Overlay and return this Overlay.

        Args:
            plot_time_points (bool): Whether to include markers for the data points.

        Returns:
            A Holoviews Overlay object.
        """
        times, values = self.waveform.get_value()

        overlay = hv.Overlay()

        # Prevent updating the plot if there are no tendencies, for example when a
        # YAML error is encountered
        if not self.waveform.tendencies:
            return overlay

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
