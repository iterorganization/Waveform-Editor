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


class State:
    """Simple state object to suppress declarative logic.

    Example:

        .. code-block:: python

            ignore_clicks = State()
            def process(obj):
                if ignore_clicks:
                    return
                ...
            widget = pn.widgets.Button(name="Process", on_click=process)

            # Elsewhere we can use a with statement to temporarily ignore clicks:
            with ignore_clicks:
                # process will not do anything, even though the on_click triggers
                widget.clicks = 0
    """

    def __init__(self):
        self.state = False

    def __bool__(self):
        return self.state

    def __enter__(self):
        if self.state:
            raise RuntimeError("Cannot enter context manager twice")
        self.state = True

    def __exit__(self, type, value, traceback):
        if not self.state:
            raise RuntimeError("Unexpected state")
        self.state = False
