import csv
import io

import imas
import numpy as np
from imas.ids_path import IDSPath
from imas.ids_struct_array import IDSStructArray

AVAILABLE_DD_VERSIONS = imas.dd_zip.dd_xml_versions()
LATEST_DD_VERSION = imas.dd_zip.latest_dd_version()


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


def has_slice(path):
    """Whether any segment of ``path`` carries a slice -- as opposed to an explicit
    index, which names exactly one element and so doesn't multiply anything."""
    return any(isinstance(index, slice) for _, index in IDSPath(path).items())


def expand(root, path):
    """Yield the node at ``path`` under ``root``, once per element it covers."""
    yield from _expand(root, list(IDSPath(path).items()))


def _expand(node, segments):
    for i, (name, index) in enumerate(segments):
        node = node[name]
        if not isinstance(node, IDSStructArray):
            continue
        if isinstance(index, int):
            node = node[index]  # an explicit index names exactly one element
            continue
        if index is None:  # addressed without an index: every element
            covered = range(len(node))
        else:
            start = index.start or 0
            stop = index.stop if index.stop is not None else len(node)
            covered = range(start, min(stop, len(node)))
        for k in covered:
            yield from _expand(node[k], segments[i + 1 :])
        return
    yield node
