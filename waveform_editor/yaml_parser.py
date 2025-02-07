import holoviews as hv
import param
import yaml

from waveform_editor.waveform import Waveform


class YamlParser(param.Parameterized):
    waveform = param.ClassSelector(
        class_=Waveform,
        default=None,
        doc="Waveform that contains the tendencies.",
    )
    annotations = param.List()

    def parse_waveforms_from_file(self, file_path):
        """Loads a YAML file from a file path and stores its tendencies into a list.

        Args:
            file_path: File path of the YAML file.
        """
        with open(file_path) as file:
            waveform_yaml = yaml.load(file, yaml.SafeLoader)
        waveform = waveform_yaml.get("waveform", [])
        self.waveform = Waveform(waveform)

    def parse_waveforms_from_string(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        try:
            waveform_yaml = yaml.load(yaml_str, yaml.SafeLoader)
            waveform = waveform_yaml.get("waveform", [])
            self.waveform = Waveform(waveform)
            self.annotations.clear()
        except yaml.YAMLError as e:
            self.annotations = self.yaml_error_to_annotation(e)
            self.waveform = None

    def yaml_error_to_annotation(self, error):
        annotations = []

        print(f"Encountered the following YAMLError:\n {error}")
        if hasattr(error, "problem_mark"):
            line = error.problem_mark.line
            column = error.problem_mark.column
            message = error.problem

            annotations.append(
                {
                    "row": line,
                    "column": column,
                    "text": f"Error: {message}",
                    "type": "error",
                }
            )
        else:
            annotations.append(
                {"row": 0, "column": 0, "text": "Unknown YAML error", "type": "error"}
            )

        return annotations

    def plot_empty(self):
        overlay = hv.Overlay()

        # Force re-render by plotting an empty plot
        overlay = overlay * hv.Curve([], "Time (s)", "Value")
        return overlay.opts(title="Waveform", width=800, height=400)

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
