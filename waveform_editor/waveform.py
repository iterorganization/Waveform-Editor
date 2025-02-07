import difflib
from typing import Optional

import numpy as np

from waveform_editor.annotations import Annotations
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
        self.annotations = Annotations()
        self._process_waveform(waveform)

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Get the tendency values at the provided time array. If no time array is
        provided, the individual tendencies are responsible for creating a time array,
        and these are appended.

        Args:
            time: The time array on which to generate points.

        Returns:
            Tuple containing the time and its tendency values.
        """
        if time is None:
            time, values = zip(*(t.get_value() for t in self.tendencies))
            time = np.concatenate(time)
            values = np.concatenate(values)
        else:
            values = self._evaluate_tendencies(time)

        return time, values

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        """Get the values of the derivatives at the provided time array.

        Args:
            time: The time array on which to generate points.

        Returns:
            numpy array containing the derivatives
        """
        return self._evaluate_tendencies(time, eval_derivatives=True)

    def _evaluate_tendencies(self, time, eval_derivatives=False):
        """Evaluates the values (or derivatives) of the tendencies at the provided
        time array.

        Args:
            time: The time array on which to generate points.
            eval_derivatives: When this is True, the derivatives will be evaluated.
                When it is False, the values will be evaluated.

        Returns:
            numpy array containing the computed values.
        """
        values = np.zeros_like(time, dtype=float)

        for tendency in self.tendencies:
            mask = (time >= tendency.start) & (time <= tendency.end)
            if np.any(mask):
                if eval_derivatives:
                    values[mask] = tendency.get_derivative(time[mask])
                else:
                    _, values[mask] = tendency.get_value(time[mask])

        return values

    def calc_length(self):
        """Returns the length of the waveform."""
        return self.tendencies[-1].end - self.tendencies[0].start

    def _process_waveform(self, waveform):
        """Processes the waveform YAML and populates the tendencies list.

        Args:
            waveform_yaml: Parsed YAML data.
        """
        for entry in waveform:
            tendency = self._handle_tendency(entry)
            if tendency is not None:
                self.tendencies.append(tendency)

        for i in range(1, len(self.tendencies)):
            self.tendencies[i - 1].set_next_tendency(self.tendencies[i])
            self.tendencies[i].set_previous_tendency(self.tendencies[i - 1])

        for tendency in self.tendencies:
            if tendency.annotations.get() != []:
                self.annotations.add_annotations(tendency.annotations)

    def _handle_tendency(self, entry):
        """Creates a tendency instance based on the entry in the YAML file.

        Args:
            entry: Entry in the YAML file.

        Returns:
            The created tendency or None, if the tendency cannot be created
        """
        tendency_type = entry.pop("type")

        # Rewrite keys
        params = {f"user_{key}": value for key, value in entry.items()}

        if tendency_type in tendency_map:
            tendency_class = tendency_map[tendency_type]
            tendency = tendency_class(**params)
            return tendency
        else:
            line_number = entry.pop("line_number")
            suggestion = self.annotations.suggest(tendency_type, tendency_map.keys())

            error_msg = (
                f"Unsupported tendency type: '{tendency_type}'.\n"
                f"Did you mean {suggestion}? \n"
                "This tendency will be ignored."
            )
            self.annotations.add(line_number, error_msg, is_warning=True)
            return None
