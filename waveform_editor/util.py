import csv

import numpy as np


def times_from_csv(csv_file):
    """Parse the CSV file containing time values.

    Args:
        csv_file: CSV file containing a single row of time values.

    Returns:
        Numpy array containing the times to export or None if no csv_file is given.
    """
    if csv_file is None:
        return None

    with open(csv_file, newline="") as file:
        reader = csv.reader(file)
        rows = list(reader)

        if len(rows) != 1:
            raise ValueError(
                "Invalid csv file. Ensure the times CSV contains a single row of "
                "comma-separated values.\nFor example: 1,2,3,4\n"
            )

        # Parse the single row into floats
        time_array = [float(value) for value in rows[0]]

    return np.array(time_array)
