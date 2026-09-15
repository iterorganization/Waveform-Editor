import numpy as np


def merge_value_types(types):
    """Determine a single value type from a collection of value types. Mixing
    ``int`` and ``float`` is allowed and results in ``float``, any other mix of
    distinct types is not allowed.

    Args:
        types: An iterable of ``int``, ``float``, and/or ``str`` types.

    Returns:
        The merged type, or None if the types cannot be merged.
    """
    types = set(types)
    if types <= {int, float}:
        return float if float in types else int
    if len(types) == 1:
        return types.pop()
    return None


def validate_time_array(annotations, line_number, time, value):
    """Validate a ``time`` list paired with a ``value`` list: both must be given,
    have the same non-zero length, and ``time`` must be finite and strictly
    monotonically increasing.

    Args:
        annotations: The Annotations instance to report problems to.
        line_number: The line number to attach any error to.
        time: List of time points.
        value: List of values paired with the time points.

    Returns:
        The validated time array or None if invalid.
    """
    if time is None or value is None:
        annotations.add(
            line_number, "Both the `time` and `value` arrays must be specified.\n"
        )
        return None
    if len(time) != len(value):
        annotations.add(
            line_number,
            "The provided time and value arrays are not of the same length.\n",
        )
        return None
    if len(time) < 1:
        annotations.add(
            line_number,
            "The provided time and value arrays should have a length of at least 1.\n",
        )
        return None

    try:
        time = np.asarray_chkfinite(time, dtype=float)
        if not np.all(np.diff(time) > 0):
            annotations.add(
                line_number,
                "The provided time array is not monotonically increasing.\n",
            )
            return None
    except Exception as error:
        annotations.add(line_number, str(error))
        return None

    return time


class InconsistentInputsError(ValueError):
    """Error raised when the input is inconsistent with the constraint matrix"""


def solve_with_constraints(inputs, constraint_matrix):
    """Solve or verify linear system under constraints.

    When inputs contains any None values, the missing values are determined. We solve
    the linear system ``constraint_matrix @ outputs == 0``, with the additional
    constraint that ``output[i] == input[i]`` for each non-None element in input.

    When all inputs are not-None, verify that the linear system adheres to:
    ``constraint_matrix @ inputs == 0`` and raise an InconstentInputsError if that is
    not the case.
    """
    if any(var is None for var in inputs):
        # Solve constraint problem
        solution = [0.0] * len(constraint_matrix)
        for i, var in enumerate(inputs):
            if var is not None:
                line = [0.0] * len(inputs)
                line[i] = 1.0
                constraint_matrix.append(line)
                solution.append(var)

        return tuple(np.linalg.solve(constraint_matrix, solution))

    # Determine if inputs are consistent
    if not np.allclose(np.array(constraint_matrix) @ inputs, 0.0):
        raise InconsistentInputsError()

    return tuple(inputs)
