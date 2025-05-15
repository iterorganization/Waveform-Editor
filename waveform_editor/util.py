import csv
import io

import numpy as np


def times_from_csv(source, from_file_path=True):
    """Parse the CSV file or utf8-encoded content containing time values.

    Args:
        source: Either a file path or utf8-encoded content from FileInput.
        from_file_path: If True, treat source as a file path. If False, treat as
            utf8-encoded bytes.

    Returns:
        Numpy array containing the times or None if the source is None.
    """
    if source is None:
        return None

    if from_file_path:
        with open(source, newline="") as file:
            reader = csv.reader(file)
            rows = list(reader)
    else:
        file_str = io.StringIO(source.decode("utf-8"))
        reader = csv.reader(file_str)
        rows = list(reader)

    if len(rows) != 1:
        raise ValueError(
            "Invalid CSV format. Expected a single row of comma-separated values.\n"
            "Example: 1,2,3,4"
        )

    # Convert string values to floats
    time_array = [float(value) for value in rows[0]]
    return np.array(time_array)
