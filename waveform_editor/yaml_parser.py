import plotly.graph_objs as go
import yaml

from waveform_editor.tendencies.base import TimeInterval
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency


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
        """Plot the tendencies in a Plotly figure and return this figure.

        Returns:
            A Plotly figure object.
        """

        fig = go.Figure()

        for tendency in self.tendencies:
            time, values = tendency.generate()
            fig.add_trace(
                go.Scatter(x=time, y=values, mode="lines", name=type(tendency).__name__)
            )
            if plot_time_points:
                fig.add_trace(
                    go.Scatter(
                        x=time,
                        y=values,
                        mode="markers",
                        marker=dict(size=3, symbol="circle", color="red"),
                        name=f"{type(tendency).__name__} - Points",
                    )
                )
        fig.update_layout(
            title="Waveform",
            xaxis_title="Time (s)",
            yaxis_title="Value",
            legend_title="Tendencies",
        )

        return fig

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
        time_interval = self._create_time_interval(entry)
        tendency_type = entry.get("type")
        if tendency_type == "linear":
            tendency = LinearTendency(
                time_interval,
                **self._filter_kwargs(entry, {"from_value": "from", "to_value": "to"}),
            )
        elif tendency_type == "sine-wave":
            tendency = SineWaveTendency(
                time_interval,
                **self._filter_kwargs(
                    entry,
                    {
                        "base": "base",
                        "amplitude": "amplitude",
                        "frequency": "frequency",
                    },
                ),
            )
        elif tendency_type == "triangle-wave":
            tendency = TriangleWaveTendency(
                time_interval,
                **self._filter_kwargs(
                    entry,
                    {
                        "base": "base",
                        "amplitude": "amplitude",
                        "frequency": "frequency",
                    },
                ),
            )
        elif tendency_type == "sawtooth-wave":
            tendency = SawtoothWaveTendency(
                time_interval,
                **self._filter_kwargs(
                    entry,
                    {
                        "base": "base",
                        "amplitude": "amplitude",
                        "frequency": "frequency",
                    },
                ),
            )
        elif tendency_type == "constant":
            tendency = ConstantTendency(
                time_interval,
                **self._filter_kwargs(entry, {"value": "value"}),
            )
        elif tendency_type == "smooth":
            tendency = SmoothTendency(
                time_interval,
                **self._filter_kwargs(entry, {"from_value": "from", "to_value": "to"}),
            )
        else:
            raise NotImplementedError(f"Unsupported tendency type: {type}")

        return tendency

    def _filter_kwargs(self, entry, key_map):
        """Helper to filter kwargs from the YAML dictionary, excluding None values. For
        example, setting `key_map={"to_value": "to"}` will look for the value of "to" in
        the entry and return it under the key "to_value" in the result.

        Args:
            entry: Entry in the YAML file.
            key_map: A mapping of argument names to entry keys.
        """

        return {
            arg: entry.get(entry_key)
            for arg, entry_key in key_map.items()
            if entry.get(entry_key) is not None
        }

    def _create_time_interval(self, entry):
        """Creates an instance of the TimeInterval dataclass, which stores the start,
        duration, and end values that the user provided.

        Args:
            entry: Entry in the YAML file.
        """
        start = entry.get("start")
        duration = entry.get("duration")
        end = entry.get("end")
        time_interval = TimeInterval(start=start, duration=duration, end=end)
        return time_interval
