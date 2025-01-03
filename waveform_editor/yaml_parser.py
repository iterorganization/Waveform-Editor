import plotly.graph_objs as go
import yaml

from waveform_editor.tendencies.base_tendency import TimeInterval
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.sine_wave import SineWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency


class YamlParser:
    def __init__(self):
        self.tendencies = []

    def parse_waveforms(self, yaml_str):
        """Loads a yaml file and stores its tendencies into a list.

        Args:
            file_path: File path of the yaml file.
        """
        # with open(file_path) as file:
        waveform_yaml = yaml.load(yaml_str, yaml.SafeLoader)

        prev_tendency = None
        for entry in waveform_yaml.get("waveform", []):
            tendency = self._handle_tendency(entry, prev_tendency)
            self.tendencies.append(tendency)
            prev_tendency = tendency

    def _handle_tendency(self, entry, prev_tendency):
        """Creates a tendency instance based on the entry in the yaml file.

        Args:
            entry: Entry in the yaml file.
            prev_tendency: Tendency which occurred previously, or None if it is the
                first tendency.
        """
        time_interval = self._create_time_interval(entry)
        tendency_type = entry.get("type")
        if tendency_type == "linear":
            tendency = LinearTendency(
                prev_tendency,
                time_interval,
                **self._filter_kwargs(entry, {"from_value": "from", "to_value": "to"}),
            )
        elif tendency_type == "sine-wave":
            tendency = SineWaveTendency(
                prev_tendency,
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
                prev_tendency,
                time_interval,
                **self._filter_kwargs(entry, {"value": "value"}),
            )
        elif tendency_type == "smooth":
            tendency = SmoothTendency(
                prev_tendency,
                time_interval,
                **self._filter_kwargs(entry, {"from_value": "from", "to_value": "to"}),
            )
        else:
            raise NotImplementedError(f"Unsupported tendency type: {type}")

        return tendency

    def _filter_kwargs(self, entry, key_map):
        """Helper to filter kwargs from the yaml dictionary, excluding None values. For
        example, setting `key_map={"to_value": "to"}` will look for the value of "to" in
        the entry and return it under the key "to_value" in the result.

        Args:
            entry: Entry in the yaml file.
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
            entry: Entry in the yaml file.
        """
        start = entry.get("start")
        duration = entry.get("duration")
        end = entry.get("end")
        time_interval = TimeInterval(start=start, duration=duration, end=end)
        return time_interval

    def plot_tendencies(self, sampling_rate=100):
        """Plot the tendencies in a Plotly figure.

        Args:
            sampling_rate: Sampling rate of the time array.
        Returns:
            A Plotly figure object.
        """

        fig = go.Figure()

        for tendency in self.tendencies:
            time, values = tendency.generate(sampling_rate=sampling_rate)
            fig.add_trace(
                go.Scatter(x=time, y=values, mode="lines", name=type(tendency).__name__)
            )

        fig.update_layout(
            title="Waveform",
            xaxis_title="Time (s)",
            yaxis_title="Value",
            legend_title="Tendencies",
        )

        return fig
