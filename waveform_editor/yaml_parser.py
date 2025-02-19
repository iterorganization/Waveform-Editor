import holoviews as hv
import yaml

from waveform_editor.waveform import Waveform


class LineNumberYamlLoader(yaml.SafeLoader):
    def _check_for_duplicates(self, node, deep):
        seen = set()

        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                # Mock a problem mark so we can pass the line number of the error
                problem_mark = yaml.Mark(
                    "<duplicate>", 0, node.start_mark.line, 0, 0, 0
                )
                raise yaml.MarkedYAMLError(
                    problem=f"Found duplicate entry {key!r}.",
                    problem_mark=problem_mark,
                )
            seen.add(key)

    def construct_mapping(self, node, deep=False):
        # The line numbers must be extracted to be able to display the error messages
        mapping = super().construct_mapping(node, deep)

        # Prepend "user_" to all keys
        mapping = {f"user_{key}": value for key, value in mapping.items()}
        mapping["line_number"] = node.start_mark.line

        # Check if all entries of the duplicate mapping are unique, as the yaml
        # SafeLoader silently ignores duplicate keys
        self._check_for_duplicates(node, deep)

        return mapping


class YamlParser:
    def __init__(self):
        self.waveform = Waveform()

    def parse_waveforms(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        self.has_yaml_error = False
        try:
            waveform_yaml = yaml.load(yaml_str, Loader=LineNumberYamlLoader)

            if not isinstance(waveform_yaml, dict):
                raise yaml.YAMLError(
                    f"Expected a dictionary but got {type(waveform_yaml).__name__!r}"
                )

            waveform = waveform_yaml.get("user_waveform", [])
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
