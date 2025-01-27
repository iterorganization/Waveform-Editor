import holoviews as hv
import yaml

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
from waveform_editor.tendencies.smooth import SmoothTendency

tendency_map = {
    "linear": LinearTendency,
    "sine-wave": SineWaveTendency,
    "sine": SineWaveTendency,
    "triangle-wave": TriangleWaveTendency,
    "triangle": TriangleWaveTendency,
    "sawtooth-wave": SawtoothWaveTendency,
    "sawtooth": SawtoothWaveTendency,
    "square-wave": SquareWaveTendency,
    "square": SquareWaveTendency,
    "constant": ConstantTendency,
    "smooth": SmoothTendency,
    "piecewise": PiecewiseLinearTendency,
}


class YamlParser:
    def __init__(self):
        self.tendencies = []

    def parse_waveforms_from_file(self, file_path):
        """Loads a YAML file from a file path and stores its tendencies into a list.

        Args:
            file_path: File path of the YAML file.
        """
        self.tendencies = []
        with open(file_path) as file:
            waveform_yaml = yaml.load(file, yaml.SafeLoader)
        self._process_waveform_yaml(waveform_yaml)

    def parse_waveforms_from_string(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        self.tendencies = []
        waveform_yaml = yaml.load(yaml_str, yaml.SafeLoader)
        self._process_waveform_yaml(waveform_yaml)

    def plot_tendencies(self, plot_time_points=False):
        """
        Plot the tendencies in a Holoviews Overlay and return this Overlay.

        Args:
            plot_time_points (bool): Whether to include markers for the data points.

        Returns:
            A Holoviews Overlay object.
        """
        times = []
        values = []

        for tendency in self.tendencies:
            time, value = tendency.generate()
            times.extend(time)
            values.extend(value)

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

    def _process_waveform_yaml(self, waveform_yaml):
        """Processes the waveform YAML and populates the tendencies list.

        Args:
            waveform_yaml: Parsed YAML data.
        """
        for entry in waveform_yaml.get("waveform", []):
            tendency = self._handle_tendency(entry)
            self.tendencies.append(tendency)

        for i in range(len(self.tendencies)):
            if i < len(self.tendencies) - 1:
                self.tendencies[i].set_next_tendency(self.tendencies[i + 1])
            if i > 0:
                self.tendencies[i].set_previous_tendency(self.tendencies[i - 1])

    def _handle_tendency(self, entry):
        """Creates a tendency instance based on the entry in the YAML file.

        Args:
            entry: Entry in the YAML file.
        """
        tendency_type = entry.pop("type")

        # Rewrite keys
        params = {f"user_{key}": value for key, value in entry.items()}

        if tendency_type in tendency_map:
            tendency_class = tendency_map[tendency_type]
            tendency = tendency_class(**params)
            return tendency
        else:
            raise NotImplementedError(f"Unsupported tendency type: {tendency_type}")
