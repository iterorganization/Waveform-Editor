import numpy as np

from waveform_editor.tendencies.base import BaseTendency
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
from waveform_editor.tendencies.repeat import RepeatTendency
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
    "repeat": RepeatTendency,
}


class Waveform:
    def __init__(self, waveform):
        self.tendencies = []
        self._process_waveform(waveform)
        self.calc_length()

    def generate(self, time=None):
        """Generate time and values based on the tendency. If no time array is provided,
        a constant line containing the start and end points will be generated.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        times = []
        values = []
        if time is None:
            for tendency in self.tendencies:
                time, value = tendency.generate()
                times.extend(time)
                values.extend(value)
        else:
            for tendency in self.tendencies:
                time = np.atleast_1d(time)
                relevant_times = time[(tendency.start <= time) & (time < tendency.end)]

                if relevant_times.size > 0:
                    time_segment, value_segment = tendency.generate(relevant_times)
                    times.extend(time_segment)
                    values.extend(value_segment)

        times = np.array(times)
        values = np.array(values)
        return times, values

    def get_start_value(self) -> float:
        """Returns the value of the tendency at the start."""
        return self.generate(self.start)

    def get_end_value(self) -> float:
        """Returns the value of the tendency at the end."""
        return self.generate(self.end)

    def get_derivative_start(self) -> float:
        """Returns the derivative of the tendency at the start."""
        # TODO:
        return 0

    def get_derivative_end(self) -> float:
        """Returns the derivative of the tendency at the end."""
        # TODO:
        return 0

    def calc_length(self):
        self.tendency_length = 0
        for tendency in self.tendencies:
            self.tendency_length += tendency.duration
        return self.tendency_length

    def _process_waveform(self, waveform):
        """Processes the waveform YAML and populates the tendencies list.

        Args:
            waveform_yaml: Parsed YAML data.
        """
        for entry in waveform:
            tendency = self._handle_tendency(entry)
            self.tendencies.append(tendency)

        for i in range(1, len(self.tendencies)):
            self.tendencies[i - 1].set_next_tendency(self.tendencies[i])
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
