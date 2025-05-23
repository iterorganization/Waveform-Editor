"""Top-level package for Waveform Editor."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("waveform_editor")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+unknown"
