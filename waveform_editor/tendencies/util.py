import numpy as np


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
