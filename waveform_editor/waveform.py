import io
from typing import Optional

import imas
import numpy as np
from imas.ids_path import IDSPath
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

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
    def __init__(
        self,
        *,
        waveform=None,
        yaml_str="",
        line_number=0,
        is_repeated=False,
        name="waveform",
        dd_version=None,
    ):
        yaml_dict = YAML().load(yaml_str)
        self.yaml = yaml_dict[name] if yaml_dict else None
        self.tendencies = []
        self.name = name
        self.line_number = line_number
        self.annotations = Annotations()
        self.is_repeated = is_repeated
        self.metadata = self.get_metadata(dd_version)
        self.units = self.metadata.units if self.metadata else "a.u."
        if waveform is not None:
            if isinstance(waveform, list):
                self._process_waveform(waveform)
            elif isinstance(waveform, (int, float)):
                self._process_number_as_waveform(waveform)

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

    def get_metadata(self, dd_version):
        """Parses the name of the waveform and returns the IDS metadata for this
        waveform. The name must be formatted as follows: ``<IDS-Name>/<IDS-path>``

        For example: ``ec_launchers/beam(2)/phase/angle``

        Args:
            dd_version: Data dictionary version to create metadata for.

        Returns:
            The metadata of the IDS node, or None if it could not find it.
        """
        try:
            ids_name, path = self.name.split("/", 1)
            dd_path = IDSPath(path)
            ids = imas.IDSFactory(version=dd_version).new(ids_name)
            return dd_path.goto_metadata(ids.metadata)
        except (imas.exception.IDSNameError, ValueError):
            return None

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

        for i, tendency in enumerate(self.tendencies):
            mask = (time >= tendency.start) & (time <= tendency.end)
            if np.any(mask):
                if eval_derivatives:
                    values[mask] = tendency.get_derivative(time[mask])
                else:
                    _, values[mask] = tendency.get_value(time[mask])

            # Handle gaps between tendencies, we linearly interpolate between the
            # gap values.
            if i and tendency.prev_tendency.end < tendency.start:
                prev_tendency = tendency.prev_tendency
                mask = (time < tendency.start) & (time > prev_tendency.end)
                slope = (tendency.start_value - prev_tendency.end_value) / (
                    tendency.start - prev_tendency.end
                )
                if np.any(mask):
                    if eval_derivatives:
                        values[mask] = slope
                    else:
                        values[mask] = np.interp(
                            time[mask],
                            [prev_tendency.end, tendency.start],
                            [prev_tendency.end_value, tendency.start_value],
                        )
        # Handle extrapolation
        if eval_derivatives:
            values[time < self.tendencies[0].start] = 0
            values[time > self.tendencies[-1].end] = 0
        else:
            first_tendency = self.tendencies[0]
            values[time < first_tendency.start] = first_tendency.start_value

            last_tendency = self.tendencies[-1]
            values[time > last_tendency.end] = last_tendency.end_value
        return values

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

    def _process_number_as_waveform(self, value):
        """Create a constant tendency when the waveform contains a single value. This
        allows for a single number to be interpreted as a constant tendency.

        For example, the YAML notation ``waveform: 1.42e6`` will be treated the same as
        ``waveform: {type: constant, value: 1.42e6}``.

        Args:
            value: The value of the constant tendency
        """
        entry = {
            "user_type": "constant",
            "user_value": value,
            "line_number": self.line_number,
        }
        tendency = self._handle_tendency(entry)
        if tendency is not None:
            self.tendencies.append(tendency)
        self.update_annotations()

    def update_annotations(self, event=None):
        """Merges the annotations of the individual tendencies into the annotations
        of this waveform."""

        for tendency in self.tendencies:
            if tendency.annotations and tendency.annotations not in self.annotations:
                self.annotations.add_annotations(tendency.annotations)

    def _has_type_error(self, entry):
        """Check if the YAML entry contains an error related to the tendency type.

        Args:
            entry: Entry in the YAML file.

        Returns:
            True if there is a type error, False otherwise.
        """
        line_number = entry.get("line_number", 0)
        ignore_msg = "This tendency will be ignored.\n"

        # If no type is given, take linear as default
        if "user_type" not in entry:
            entry["user_type"] = "linear"

        tendency_type = entry.get("user_type", None)
        if tendency_type is None:
            error_msg = f"The tendency type cannot be empty.\n{ignore_msg}"
            self.annotations.add(line_number, error_msg)
            return True

        if not isinstance(tendency_type, str):
            error_msg = f"The tendency type should be of type 'string'.\n{ignore_msg}"
            self.annotations.add(line_number, error_msg)
            return True

        if tendency_type not in tendency_map:
            suggestion = self.annotations.suggest(tendency_type, tendency_map.keys())

            error_msg = (
                f"Unsupported tendency type: '{tendency_type}'. {suggestion}"
                f"{ignore_msg}"
            )
            self.annotations.add(line_number, error_msg)
            return True
        return False

    def get_yaml_string(self):
        """Converts the internal YAML waveform description to a string.

        Returns:
            The YAML waveform description as a string.
        """
        if isinstance(self.yaml, CommentedSeq):
            # Dump using ruamel to preserve YAML structure and comments
            stream = io.StringIO()
            YAML().dump(self.yaml, stream)
            return stream.getvalue()
        elif self.yaml is None:
            raise ValueError(
                f"Waveform '{self.name}' has not been assigned a valid YAML object."
            )
        else:
            return str(self.yaml)

    def _handle_tendency(self, entry):
        """Creates a tendency instance based on the entry in the YAML file.

        Args:
            entry: Entry in the YAML file.

        Returns:
            The created tendency or None, if the tendency cannot be created
        """
        if self._has_type_error(entry):
            return None
        else:
            tendency_type = entry.pop("user_type")
            tendency_class = tendency_map[tendency_type]
            tendency = tendency_class(**entry)
            return tendency
