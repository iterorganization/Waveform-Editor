from abc import ABC, abstractmethod

import imas
from imas.ids_data_type import IDSDataType
from imas.ids_path import IDSPath
from ruamel.yaml import YAML

from waveform_editor.annotations import Annotations

_DD_TYPE_TO_PYTHON = {
    IDSDataType.FLT: float,
    IDSDataType.INT: int,
    IDSDataType.STR: str,
}


class ConfigEntry(ABC):
    is_time_trace = True

    def __init__(self, yaml_str, name, dd_version):
        yaml_dict = YAML().load(yaml_str)
        self.yaml = yaml_dict[name] if yaml_dict else None
        self.name = name
        self.metadata = self.get_metadata(dd_version)
        self.annotations = Annotations()
        self.units = self.metadata.units if self.metadata else "a.u."
        self.value_type = (
            _DD_TYPE_TO_PYTHON.get(self.metadata.data_type, float)
            if self.metadata
            else float
        )

    @abstractmethod
    def get_yaml_string(self) -> str:
        raise NotImplementedError

    def get_metadata(self, dd_version):
        """Parses the name of the waveform and returns the IDS metadata for this
        waveform. The name must be formatted as follows: ``<IDS-Name>/<IDS-path>``

        For example: ``ec_launchers/beam(2)/phase/angle``

        Args:
            dd_version: Data dictionary version to create metadata for.

        Returns:
            The metadata of the IDS node, or None if it could not find it.
        """
        try:
            ids_name, path = self.name.split("/", 1)
            dd_path = IDSPath(path)
            ids = imas.IDSFactory(version=dd_version).new(ids_name)
            return dd_path.goto_metadata(ids.metadata)
        except (imas.exception.IDSNameError, ValueError):
            return None
