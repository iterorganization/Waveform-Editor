import logging
import re
from io import StringIO

import yaml
from ruamel.yaml import YAML

from waveform_editor.group import WaveformGroup
from waveform_editor.waveform import Waveform

logger = logging.getLogger(__name__)


class LineNumberYamlLoader(yaml.SafeLoader):
    def _check_for_duplicates(self, node, deep):
        seen = set()

        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                # Mock a problem mark so we can pass the line number of the error
                problem_mark = yaml.Mark(
                    "<duplicate>", 0, node.start_mark.line, 0, 0, 0
                )
                raise yaml.MarkedYAMLError(
                    problem=f"Found duplicate entry {key!r}.",
                    problem_mark=problem_mark,
                )
            seen.add(key)

    def construct_mapping(self, node, deep=False):
        # The line numbers must be extracted to be able to display the error messages
        mapping = super().construct_mapping(node, deep)

        # Prepend "user_" to all keys
        mapping = {f"user_{key}": value for key, value in mapping.items()}
        mapping["line_number"] = node.start_mark.line

        # Check if all entries of the duplicate mapping are unique, as the yaml
        # SafeLoader silently ignores duplicate keys
        self._check_for_duplicates(node, deep)

        return mapping


class YamlParser:
    def __init__(self, config):
        self.yaml = YAML()
        self.config = config
        self.parse_errors = []

    def load_yaml(self, yaml_str):
        """Parses a YAML string and builds waveform groups and a waveform map.

        Args:
            yaml_str: The YAML string to load YAML for.
        Returns:
            A dictionary containing 'groups' and 'waveform_map', or None on error.
        """
        self.parse_errors = []
        self.config.clear()
        try:
            yaml_data = self.yaml.load(yaml_str)
            globals = yaml_data.get("globals", {})
            self.config.dd_version = globals.get("dd_version")
            md_dict = globals.get("machine_description", {})
            if not isinstance(md_dict, dict):
                raise ValueError("The machine description must be a dictionary")

            self.config.machine_description = md_dict

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

                root_group = self._recursive_load(group_content, group_name)
                self.config.groups[group_name] = root_group

            if self.parse_errors:
                raise ValueError("\n".join(self.parse_errors))
        except Exception as e:
            self.config.clear()
            logger.warning("Got unexpected error: %s", e, exc_info=e)
            self.config.load_error = str(e)

    def _recursive_load(self, data_dict, group_name):
        """Recursively builds a hierarchy of WaveformGroup objects from a nested
        dictionary.

        Groups are represented by dictionaries without '/' in their keys.
        Waveforms are key-value pairs where keys contain '/'.

        Args:
            data_dict: Input data containing waveform groups and waveforms.
            group_name: Name of the current group.

        Returns:
            The populated waveform group.
        """
        current_group = WaveformGroup(group_name)

        for key, value in data_dict.items():
            # If value is a dictionary, treat it as a group, otherwise as a waveform
            if isinstance(value, dict):
                if "/" in key:
                    raise ValueError(
                        f"Invalid group '{key}': Group names may not contain '/'."
                    )

                nested_group = self._recursive_load(value, key)
                current_group.groups[key] = nested_group
            else:
                if "/" not in key:
                    raise ValueError(
                        f"Invalid waveform name '{key}': "
                        "Waveform names must contain '/'."
                    )
                yaml_str = self.generate_yaml_str(key, value)
                waveform = self.parse_waveform(yaml_str)
                current_group.waveforms[key] = waveform
                self.config.waveform_map[key] = current_group

        return current_group

    def generate_yaml_str(self, key, value):
        """Generate YAML string for a key-value pair, ensuring comments are retained.

        Args:
            key: Key of the yaml string.
            value: Corresponding value for the key.
        """
        stream = StringIO()
        self.yaml.dump({key: value}, stream)
        return stream.getvalue()

    def parse_waveform(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        try:
            loader = LineNumberYamlLoader
            # Parse scientific notation as a float, instead of a string. For
            # more information see: https://stackoverflow.com/a/30462009/8196245
            loader.add_implicit_resolver(
                "tag:yaml.org,2002:float",
                re.compile(
                    """^(?:
                     [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
                    |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
                    |\\.[0-9_]+(?:[eE][-+][0-9]+)?
                    |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*
                    |[-+]?\\.(?:inf|Inf|INF)
                    |\\.(?:nan|NaN|NAN))$""",
                    re.X,
                ),
                list("-+0123456789."),
            )
            waveform_yaml = yaml.load(yaml_str, Loader=loader)

            if not isinstance(waveform_yaml, dict):
                raise yaml.YAMLError(
                    f"Expected a dictionary but got {type(waveform_yaml).__name__!r}"
                )

            # Find first key in the yaml that starts with "user_"
            for waveform_key in waveform_yaml:
                if waveform_key.startswith("user_"):
                    break
            else:
                raise RuntimeError("Missing key")

            name = waveform_key.removeprefix("user_")
            waveform = waveform_yaml[waveform_key]
            if waveform is None:
                raise yaml.YAMLError("Cannot have an empty waveform.")
            if not isinstance(waveform, (list, int, float)):
                raise yaml.YAMLError(
                    "Waveform must either be a list of tendencies, "
                    "or a single constant value."
                )
            line_number = waveform_yaml.get("line_number", 0)
            waveform = Waveform(
                waveform=waveform,
                yaml_str=yaml_str,
                line_number=line_number,
                name=name,
                dd_version=self.config.dd_version,
            )
            return waveform
        except yaml.YAMLError as e:
            self.parse_errors.append(str(e))
            empty_waveform = Waveform()
            empty_waveform.annotations.add_yaml_error(e)
            return empty_waveform
