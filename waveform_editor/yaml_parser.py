import matplotlib.pyplot as plt
import yaml

from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency


def handle_tendency(entry, prev_end):
    tendency_type = entry.get("type")
    match tendency_type:
        case "linear":
            tendency = LinearTendency(
                entry.get("from"),
                entry.get("to"),
                entry.get("duration"),
                prev_end,
            )
        case "sine-wave":
            tendency = None
        case "constant":
            tendency = ConstantTendency(
                entry.get("value"),
                entry.get("duration"),
                prev_end,
            )
        case "smooth":
            tendency = None
        case _:
            raise NotImplementedError(f"Unsupported tendency type: {type}")

    return tendency


def parse_waveforms(waveform_data):
    tendencies = []
    prev_end = 0
    for entry in waveform_data.get("waveform", []):
        tendency = handle_tendency(entry, prev_end)
        prev_end = tendency.end
        tendencies.append(tendency)
    return tendencies


if __name__ == "__main__":
    file_path = "test.yaml"
    with open(file_path) as file:
        waveform_data = yaml.load(file, yaml.SafeLoader)

    tendencies = parse_waveforms(waveform_data)

    for tendency in tendencies:
        time, values = tendency.generate(3)
        print(time, values)

        plt.plot(time, values, label=tendency.tendency_type)

    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title("Waveform")
    plt.legend()
    plt.show()
