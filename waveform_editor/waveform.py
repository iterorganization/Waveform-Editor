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
    def __init__(self, *, waveform=None, is_repeated=False):
        self.tendencies = []
        self.annotations = Annotations()
        self.is_repeated = is_repeated
        if waveform is not None:
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
        if not self.tendencies:
            return np.array([]), np.array([])

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
        values = np.full_like(time, np.nan, dtype=float)

        for tendency in self.tendencies:
            mask = (time >= tendency.start) & (time <= tendency.end)
            if np.any(mask):
                if eval_derivatives:
                    values[mask] = tendency.get_derivative(time[mask])
                else:
                    _, values[mask] = tendency.get_value(time[mask])

        # If there still remain nans in the values, this means that there are gaps
        # between the tendencies. In this case we linearly interpolate between the gap
        # values
        for idx, t in enumerate(time):
            if np.isnan(values[idx]):
                # The derivatives of interpolated gaps are not calculated
                if eval_derivatives:
                    values[idx] = 0
                else:
                    values[idx] = self._interpolate_gap(t)

        return values

    def _interpolate_gap(self, t):
        """Interpolates the value for a given time t based on the nearest tendencies.
        Also extrapolates the values if the time requested falls before the first, or
        after the last tendency.

        Args:
            t: The time for which the value needs to be interpolated.

        Returns:
            The interpolated value.
        """
        # Find nearest tendencies before and after time t
        prev_tendency = max(
            (tend for tend in self.tendencies if tend.end <= t),
            default=None,
            key=lambda tend: tend.end,
        )
        next_tendency = min(
            (tend for tend in self.tendencies if tend.start >= t),
            default=None,
            key=lambda tend: tend.start,
        )

        if prev_tendency and next_tendency:
            val_end = prev_tendency.end_value
            val_start = next_tendency.start_value

            return np.interp(
                t, [prev_tendency.end, next_tendency.start], [val_end, val_start]
            )

        # Handle extrapolation if t is before the first or after the last tendency
        if prev_tendency is None:
            next_tendency = self.tendencies[0]
            val_start = next_tendency.start_value
            return val_start

        if next_tendency is None:
            prev_tendency = self.tendencies[-1]
            val_end = prev_tendency.end_value
            return val_end

        # If no valid interpolation or extrapolation can be performed, return 0
        return 0.0

    def calc_length(self):
        """Returns the length of the waveform."""
        return self.tendencies[-1].end - self.tendencies[0].start

    def _process_waveform(self, waveform):
        """Processes the waveform YAML and populates the tendencies list.

        Args:
            waveform_yaml: Parsed YAML data.
        """
        if not waveform:
            error_msg = (
                "The YAML should contain a waveform. For example:\n"
                "waveform:\n- {type: constant, value: 3, duration: 5}"
            )
            self.annotations.add(0, error_msg)
            return

        for i, entry in enumerate(waveform):
            if not isinstance(entry, dict):
                error_msg = (
                    "Waveform entry should be a dictionary. For example:\n"
                    "waveform:\n- {type: constant, value: 3, duration: 5}"
                )
                self.annotations.add(0, error_msg)
                continue
            # Add key to notify the tendency is the first repeated tendency
            if i == 0:
                entry["is_first_repeated"] = self.is_repeated
            tendency = self._handle_tendency(entry)
            if tendency is not None:
                self.tendencies.append(tendency)

        for i in range(1, len(self.tendencies)):
            self.tendencies[i - 1].set_next_tendency(self.tendencies[i])
            self.tendencies[i].set_previous_tendency(self.tendencies[i - 1])

        self.update_annotations()

        for tendency in self.tendencies:
            tendency.param.watch(self.update_annotations, "annotations")

    def update_annotations(self, event=None):
        """Merges the annotations of the individual tendencies into the annotations
        of this waveform."""

        for tendency in self.tendencies:
            if tendency.annotations and tendency.annotations not in self.annotations:
                self.annotations.add_annotations(tendency.annotations)

    def _handle_tendency(self, entry):
        """Creates a tendency instance based on the entry in the YAML file.

        Args:
            entry: Entry in the YAML file.

        Returns:
            The created tendency or None, if the tendency cannot be created
        """
        if "type" not in entry:
            line_number = entry.pop("line_number")
            error_msg = (
                "The tendency must have a 'type'.\n"
                "For example: '- {type: constant, duration: 3, value: 3}'\n"
                "This tendency will be ignored."
            )
            self.annotations.add(line_number, error_msg)
            return None
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
                f"Unsupported tendency type: '{tendency_type}'. {suggestion}"
                "This tendency will be ignored.\n"
            )
            self.annotations.add(line_number, error_msg)
            return None
