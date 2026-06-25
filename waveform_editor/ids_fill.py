"""Helpers for writing values into an IDS at a given DD path.

Shared by the exporter (analytic / scalar-import waveforms) and the import resolver
(structural imports): both walk an ``IDSPath`` and resize the arrays of structure they
cross before assigning the leaf value(s).
"""


def fill_nodes(node, path, values, path_index=0):
    """Recursively fill the node at ``path`` in ``node`` with ``values``, resizing the
    arrays of structure crossed on the way to fit."""
    if path_index == len(path.parts):
        node.value = values
        return
    part = path.parts[path_index]
    index = path.indices[path_index]

    node = node[part]
    next_index = path_index + 1
    if index is None:
        if node.metadata.type.is_dynamic and part != path.parts[-1]:
            if len(node) != len(values):
                node.resize(len(values), keep=True)
            for item, value in zip(node, values, strict=True):
                fill_nodes(item, path, value, next_index)
        else:
            fill_nodes(node, path, values, next_index)
    elif isinstance(index, slice):
        start, stop = resize_slice(node, index)
        for i in range(start, stop):
            fill_nodes(node[i], path, values, next_index)
    else:
        if len(node) <= index:
            node.resize(index + 1, keep=True)
        fill_nodes(node[index], path, values, next_index)


def resize_slice(ids_node, slice_):
    """Resize ``ids_node`` to cover ``slice_`` and return its (start, stop)."""
    if slice_.start is None and slice_.stop is None:
        start = 0
        stop = len(ids_node) or 1
    else:
        start = slice_.start if slice_.start is not None else 0
        stop = slice_.stop if slice_.stop is not None else len(ids_node) or start + 1
    max_index = max(start, stop - 1)
    if len(ids_node) <= max_index:
        ids_node.resize(max_index + 1, keep=True)
    return start, stop
