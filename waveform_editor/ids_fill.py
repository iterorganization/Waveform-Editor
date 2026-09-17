"""Reading and writing values in an IDS at a given DD path.

Writing is two steps: :func:`size_arrays` grows every array of structure to the largest
size any waveform requires (so a ``:`` slice later expands against the final size, and
each array is resized once regardless of declaration order), then :func:`fill_nodes`
writes each waveform's values. A copied node reuses :func:`fill_nodes` too, and sizes
itself as it copies.

Reading is the mirror: :func:`extract` pulls the value(s) at a path out of a source
IDS, and :func:`expand_slices` turns a path containing a ``(:)`` slice into the
concrete per-element paths it covers.
"""

import re

import numpy as np
from imas.ids_path import IDSPath
from imas.ids_struct_array import IDSStructArray

#: A path segment: ``name``, ``name(2)`` or ``name(1:3)``.
_SEGMENT = re.compile(r"^([^()]+)(?:\((.*)\))?$")


def has_slice(parts):
    """Whether any of these path segments carries a ``(a:b)`` slice -- as opposed to
    an explicit index like ``(2)``, which names exactly one element and so doesn't
    multiply anything."""
    return any(":" in (_SEGMENT.match(part).group(2) or "") for part in parts)


def expand_slices(root, src_sub, dst_sub):
    """Expand every explicit slice in ``src_sub`` against the source.

    Yields concrete ``(src, dst)`` path pairs, with each ``name(a:b)`` replaced by the
    1-based index of every element it covers. A dynamic array of structure addressed
    without an index (``time_slice/...``) is normally left alone: those are read and
    written as a value per time step. It is only made concrete when a slice further
    down has to be resolved inside each of its elements separately --
    ``source(:)/profiles_1d/ion(:)`` is a different ion array in every time slice, and
    they need not all be the same length.
    """
    src_parts = src_sub.split("/")
    dst_parts = dst_sub.split("/")

    for i, segment in enumerate(src_parts):
        name, index = _SEGMENT.match(segment).groups()
        if index is None:
            if not has_slice(src_parts[i + 1 :]):
                continue
            node = IDSPath("/".join(src_parts[:i] + [name])).goto(root)
            if not isinstance(node, IDSStructArray):
                continue
            indices = range(len(node))
        elif ":" in index:
            node = IDSPath("/".join(src_parts[:i] + [name])).goto(root)
            low, _, high = index.partition(":")
            start = int(low) - 1 if low.strip() else 0
            stop = int(high) if high.strip() else len(node)
            indices = range(start, min(stop, len(node)))
        else:
            continue

        for k in indices:
            new_src = list(src_parts)
            new_dst = list(dst_parts)
            new_src[i] = f"{name}({k + 1})"
            if i < len(new_dst):
                new_dst[i] = f"{name}({k + 1})"
            yield from expand_slices(root, "/".join(new_src), "/".join(new_dst))
        return

    yield src_sub, dst_sub


def extract(node, path, path_index=0):
    """The value(s) at ``path``, as a per-element list wherever the path crosses an
    array of structure without a single index -- the mirror of :func:`fill_nodes`."""
    if path_index == len(path.parts):
        return node.value
    part = path.parts[path_index]
    index = path.indices[path_index]
    node = node[part]
    next_index = path_index + 1
    if index is None:
        if node.metadata.type.is_dynamic and part != path.parts[-1]:
            return [extract(item, path, next_index) for item in node]
        return extract(node, path, next_index)
    if isinstance(index, slice):
        start, stop = resize_slice(node, index)
        return [extract(node[i], path, next_index) for i in range(start, stop)]
    return extract(node[index], path, next_index)


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
        if (
            node.metadata.ndim == 0
            and isinstance(values, np.ndarray)
            and values.ndim > 0
        ):
            # A 0D destination leaf can still receive a per-time array:
            # ImportReader.sample() broadcasts a static source across the export time
            # base so every waveform can be treated uniformly. All elements are
            # identical for a genuinely static source, so collapse back to a single
            # value rather than assigning a multi-element array to a 0D leaf (which
            # imas-python's scalar cast rejects). The test is the destination's rank,
            # not whether it is dynamic: a static *array* (a wall outline, coil
            # geometry) must keep every element.
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
