import matplotlib.pyplot as plt
import yaml

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.sine_wave import SineWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency


class YamlParser:
    def __init__(self):
        self.tendencies = []

    def parse_waveforms(self, file_path):
        with open(file_path) as file:
            waveform_yaml = yaml.load(file, yaml.SafeLoader)

        prev_tendency = None
        for entry in waveform_yaml.get("waveform", []):
            tendency = self._handle_tendency(entry, prev_tendency)
            self.tendencies.append(tendency)
            prev_tendency = tendency

    def _handle_tendency(self, entry, prev_tendency):
        tendency_type = entry.get("type")
        if tendency_type == "linear":
            tendency = LinearTendency(
                prev_tendency,
                from_value=entry.get("from"),
                to_value=entry.get("to"),
                duration=entry.get("duration"),
            )
        elif tendency_type == "sine-wave":
            tendency = SineWaveTendency(
                prev_tendency,
                base=entry.get("base"),
                amplitude=entry.get("amplitude"),
                frequency=entry.get("frequency"),
                duration=entry.get("duration"),
            )
        elif tendency_type == "constant":
            tendency = ConstantTendency(
                prev_tendency,
                value=entry.get("value"),
                duration=entry.get("duration"),
            )
        elif tendency_type == "smooth":
            tendency = SmoothTendency(
                prev_tendency,
                from_value=entry.get("from"),
                to_value=entry.get("to"),
                duration=entry.get("duration"),
            )
        else:
            raise NotImplementedError(f"Unsupported tendency type: {type}")

        return tendency

    def plot_tendencies(self, sampling_rate=100):
        for tendency in self.tendencies:
            time, values = tendency.generate(sampling_rate=sampling_rate)

            plt.plot(time, values, "o-", label=tendency.tendency_type)

        plt.xlabel("Time (s)")
        plt.ylabel("Value")
        plt.title("Waveform")
        plt.legend()
        plt.show()
