import matplotlib.pyplot as plt
import yaml

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.sine_wave import SineWaveTendency
from waveform_editor.tendencies.smooth import SmoothTendency


def handle_tendency(entry, prev_tendency):
    tendency_type = entry.get("type")
    match tendency_type:
        case "linear":
            tendency = LinearTendency(
                prev_tendency,
                entry.get("from"),
                entry.get("to"),
                entry.get("duration"),
            )
        case "sine-wave":
            tendency = SineWaveTendency(
                prev_tendency,
                entry.get("base"),
                entry.get("amplitude"),
                entry.get("frequency"),
                entry.get("duration"),
            )
        case "constant":
            tendency = ConstantTendency(
                prev_tendency,
                entry.get("value"),
                entry.get("duration"),
            )
        case "smooth":
            tendency = SmoothTendency(
                prev_tendency,
                from_value=entry.get("from"),
                to_value=entry.get("to"),
                duration=entry.get("duration"),
            )
        case _:
            raise NotImplementedError(f"Unsupported tendency type: {type}")

    return tendency


def parse_waveforms(waveform_data):
    tendencies = []

    # Initially start at 0
    prev_tendency = None
    for entry in waveform_data.get("waveform", []):
        tendency = handle_tendency(entry, prev_tendency)
        tendencies.append(tendency)
        prev_tendency = tendency
    return tendencies


if __name__ == "__main__":
    file_path = "test_all.yaml"
    with open(file_path) as file:
        waveform_data = yaml.load(file, yaml.SafeLoader)

    tendencies = parse_waveforms(waveform_data)

    for tendency in tendencies:
        time, values = tendency.generate(100)

        plt.plot(time, values, label=tendency.tendency_type)

    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title("Waveform")
    plt.legend()
    plt.show()
