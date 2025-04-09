from io import StringIO

from ruamel.yaml import YAML

from waveform_editor.group import WaveformGroup
from waveform_editor.waveform import Waveform


class YamlParser:
    def __init__(self):
        self.load_yaml_error = ""
        self.parse_errors = []

    def load_yaml(self, yaml_str):
        groups = {}
        waveform_map = {}
        try:
            yaml_data = YAML().load(yaml_str)
            if not isinstance(yaml_data, dict):
                raise ValueError("Input yaml_data must be a dictionary.")

            for group_name, group_content in yaml_data.items():
                if group_name == "globals":
                    continue

                if "/" in group_name:
                    raise ValueError(
                        f"Invalid group name '{group_name}': "
                        "Group names may not contain '/'."
                    )
                if not isinstance(group_content, dict):
                    raise ValueError("Waveforms must belong to a group.")

                root_group = self._recursive_load(
                    group_content, group_name, waveform_map
                )
                groups[group_name] = root_group
            return {"groups": groups, "waveform_map": waveform_map}
        except Exception as e:
            self.load_yaml_error = e
            return None

    def _recursive_load(self, data_dict, group_name, waveform_map):
        current_group = WaveformGroup(group_name)

        for key, value in data_dict.items():
            # If value is a dictionary, treat it as a group, otherwise as a waveform
            if isinstance(value, dict):
                if "/" in key:
                    raise ValueError(
                        f"Invalid group '{key}': Group names may not contain '/'."
                    )
                nested_group = self._recursive_load(value, key, waveform_map)
                current_group.groups[key] = nested_group
            else:
                if "/" not in key:
                    raise ValueError(
                        f"Invalid waveform name '{key}': "
                        "Waveform names must contain '/'."
                    )
                waveform = self.parse_waveforms(key, value)
                current_group.waveforms[key] = waveform
                waveform_map[key] = current_group

        return current_group

    def parse_waveforms(self, key, value):
        """Loads a waveform from a YAML string, preserving comments and structure.

        Args:
            key: The key (name) of the waveform.
            value: The YAML content as a value for the waveform.
        """
        try:
            # Get raw YAML string
            stream = StringIO()
            YAML().dump({key: value}, stream)
            yaml_str = stream.getvalue()

            return Waveform(
                waveform=value,
                yaml_str=yaml_str,
                line_number=0,
                name=key,
            )

        except Exception as e:
            self.parse_errors.append(e)
            return Waveform()
