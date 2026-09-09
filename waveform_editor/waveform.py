import io

import numpy as np
from imas.ids_data_type import IDSDataType
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from waveform_editor.base_waveform import BaseWaveform
from waveform_editor.tendencies.constant import ConstantTendency
from waveform_editor.tendencies.linear import LinearTendency
from waveform_editor.tendencies.periodic.sawtooth_wave import SawtoothWaveTendency
from waveform_editor.tendencies.periodic.sine_wave import SineWaveTendency
from waveform_editor.tendencies.periodic.square_wave import SquareWaveTendency
from waveform_editor.tendencies.periodic.triangle_wave import TriangleWaveTendency
from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency
from waveform_editor.tendencies.repeat import RepeatTendency
from waveform_editor.tendencies.smooth import SmoothTendency
from waveform_editor.tendencies.steps import StepsTendency
from waveform_editor.tendencies.util import merge_value_types

IDS_DATATYPES = {
    float: {IDSDataType.FLT},
    str: {IDSDataType.STR},
    int: {IDSDataType.INT, IDSDataType.FLT},  # An int is also valid for a float field
}

NUMPY_DTYPE_MAP = {
    float: float,
    int: float,
    str: object,
}


TENDENCY_MAP = {
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
    "steps": StepsTendency,
}

INFERRED_TYPE_BY_KEY = {
    "user_time": PiecewiseLinearTendency,
    "user_value": ConstantTendency,
    "user_waveform": RepeatTendency,
}


def _infer_tendency_class(entry):
    """Infer a tendency's class from keys in the tendency entry, defaulting to
    linear tendency if no distinctive keys are present.

    Args:
        entry: Entry in the YAML file.

    Returns:
        The inferred tendency class.
    """
    for key, tendency_class in INFERRED_TYPE_BY_KEY.items():
        if key in entry:
            return tendency_class
    return LinearTendency


class Waveform(BaseWaveform):
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
        super().__init__(yaml_str, name, dd_version)
        self.line_number = line_number
        self.is_repeated = is_repeated
        if waveform is not None:
            self._process_waveform(waveform)

    def get_value(
        self, time: np.ndarray | None = None
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
            time, values = zip(*(t.get_value() for t in self.tendencies), strict=True)
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
        dtype = float if eval_derivatives else NUMPY_DTYPE_MAP[self.value_type]
        is_categorical = dtype is object
        values = (
            np.empty(len(time), dtype=object)
            if is_categorical
            else np.zeros_like(time, dtype=dtype)
        )

        for i, tendency in enumerate(self.tendencies):
            mask = (time >= tendency.start) & (time <= tendency.end)
            if np.any(mask):
                if eval_derivatives:
                    values[mask] = tendency.get_derivative(time[mask])
                else:
                    _, values[mask] = tendency.get_value(time[mask])

            # Handle gaps between tendencies: interpolate for numeric values, hold
            # the previous value for categorical ones.
            if i and tendency.prev_tendency.end < tendency.start:
                prev_tendency = tendency.prev_tendency
                mask = (time < tendency.start) & (time > prev_tendency.end)
                if np.any(mask):
                    if eval_derivatives:
                        values[mask] = (
                            tendency.start_value - prev_tendency.end_value
                        ) / (tendency.start - prev_tendency.end)
                    elif is_categorical:
                        values[mask] = prev_tendency.end_value
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

        self._validate_value_type()
        self.update_annotations()

        for tendency in self.tendencies:
            tendency.param.watch(self.update_annotations, "annotations")

    def _validate_value_type(self):
        """Determine this waveform's value type from its tendencies and set
        ``self.value_type`` to reflect it.
        """
        if not self.tendencies:
            return

        value_types = set(tendency.value_type for tendency in self.tendencies)
        merged_type = merge_value_types(value_types)
        if merged_type is None:
            type_names = ", ".join(sorted(t.__name__ for t in value_types))
            error_msg = (
                f"Cannot mix string and numerical tendency value types within a single "
                f"waveform. Found: {type_names}."
            )
            self.annotations.add(0, error_msg)
            return
        self.value_type = merged_type

        # If a valid DD path is chosen, check if the value_type matches the DD type
        if (
            self.metadata is not None
            and self.metadata.data_type not in IDS_DATATYPES[self.value_type]
        ):
            error_msg = (
                "Type is not valid here: this waveform expects a "
                f"{self.metadata.data_type}.\n"
            )
            self.annotations.add(self.tendencies[0].line_number, error_msg)

    def update_annotations(self, event=None):
        """Merges the annotations of the individual tendencies into the annotations
        of this waveform."""

        for tendency in self.tendencies:
            if tendency.annotations and tendency.annotations not in self.annotations:
                self.annotations.add_annotations(tendency.annotations)

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
        # If no type is given, infer it from the entry's keys
        if "user_type" not in entry:
            tendency_class = _infer_tendency_class(entry)
        else:
            user_type = entry.pop("user_type")
            user_type = "" if user_type is None else str(user_type)
            tendency_class = TENDENCY_MAP.get(user_type)
            if tendency_class is None:
                suggestion = self.annotations.suggest(user_type, TENDENCY_MAP.keys())
                error_msg = (
                    f"Unsupported tendency type: '{user_type}'. "
                    f"{suggestion}This tendency will be ignored.\n"
                )
                self.annotations.add(entry.get("line_number", 0), error_msg)
                return None

        return tendency_class(**entry)
