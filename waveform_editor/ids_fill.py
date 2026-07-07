"""Helpers for writing values into an IDS at a given DD path.

Filling is two steps: :func:`size_arrays` grows every array of structure to the largest
size any waveform requires (so a ``:`` slice later expands against the final size, and
each array is resized once regardless of declaration order), then :func:`fill_nodes`
writes each waveform's values. The resolver reuses :func:`fill_nodes` for structural
imports, which size themselves as they copy.
"""


def size_arrays(node, paths, time_len, path_index=0):
    """Resize every array of structure crossed by ``paths`` to the size it needs.

    The required size of an array is the maximum over all ``paths`` of: an explicit
    index + 1, a bounded slice's stop, or ``time_len`` for a dynamic (time-dependent)
    array addressed without an index. This is computed before resizing, so the result
    does not depend on the order of ``paths`` and each array is grown exactly once. A
    bare ``:`` and arrays with no size source contribute nothing and are grown at fill
    time instead.
    """
    groups = {}
    for path in paths:
        if path_index < len(path.parts):
            groups.setdefault(path.parts[path_index], []).append(path)

    for part, group in groups.items():
        child = node[part]
        nxt = path_index + 1

        # Decide whether `part` is an array of structure here, and its required size.
        is_array = False
        required = 0
        for path in group:
            index = path.indices[path_index]
            if isinstance(index, int):
                is_array = True
                required = max(required, index + 1)
            elif isinstance(index, slice):
                is_array = True
                if index.stop is not None:
                    required = max(required, index.stop)
            elif child.metadata.type.is_dynamic and nxt < len(path.parts):
                is_array = True  # dynamic AoS addressed without an index: one per slice
                required = max(required, time_len)

        if not is_array:
            # Plain structure (or terminal leaf): descend in place.
            size_arrays(child, group, time_len, nxt)
            continue

        if required > len(child):
            child.resize(required, keep=True)

        # Recurse into the elements each path covers, now that the array is sized.
        per_element = {}
        for path in group:
            if nxt >= len(path.parts):
                continue
            index = path.indices[path_index]
            if isinstance(index, int):
                covered = (index,)
            elif isinstance(index, slice):
                stop = index.stop if index.stop is not None else len(child)
                covered = range(index.start or 0, stop)
            else:  # dynamic AoS addressed without an index: every element
                covered = range(len(child))
            for i in covered:
                if i < len(child):
                    per_element.setdefault(i, []).append(path)
        for i, element_paths in per_element.items():
            size_arrays(child[i], element_paths, time_len, nxt)


def fill_nodes(node, path, values, path_index=0):
    """Write ``values`` at ``path`` in ``node``, growing arrays of structure crossed on
    the way to fit (so it is correct without a prior :func:`size_arrays` pass too)."""
    if path_index == len(path.parts):
        if not node.metadata.type.is_dynamic and hasattr(values, "__len__"):
            values = values[0]
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
