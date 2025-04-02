import re

import yaml

from waveform_editor.configuration import WaveformConfiguration
from waveform_editor.group import WaveformGroup
from waveform_editor.waveform import Waveform


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
    def load_yaml(self, yaml_str):
        waveform_config = WaveformConfiguration()
        try:
            yaml_data = yaml.safe_load(yaml_str)
            if not isinstance(yaml_data, dict):
                raise ValueError("Input yaml_data must be a dictionary.")

            for group_name, group_content in yaml_data.items():
                if group_name == "globals":
                    continue

                if not isinstance(group_content, dict):
                    raise ValueError("Waveforms must belong to a group.")

                root_group = self._recursive_load(group_content, group_name)
                waveform_config.groups[group_name] = root_group
        except yaml.YAMLError as e:
            # TODO: global YAML errors should be shown in an error notification in UI
            print(f"The YAML could not be parsed.\n{e}")
        return waveform_config

    def _recursive_load(self, data_dict, group_name):
        current_group = WaveformGroup(group_name)

        for key, value in data_dict.items():
            if "/" in key:
                waveform = self.parse_waveforms(yaml.dump({key: value}))
                current_group.waveforms[key] = waveform
            elif isinstance(value, dict):
                nested_group = self._recursive_load(value, key)
                current_group.groups[key] = nested_group

        return current_group

    def parse_waveforms(self, yaml_str):
        """Loads a YAML structure from a string and stores its tendencies into a list.

        Args:
            yaml_str: YAML content as a string.
        """
        self.has_yaml_error = False
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
                if waveform_key.startswith("user_") and waveform_key != "line_number":
                    break
            else:
                raise RuntimeError("Missing key")

            name = waveform_key.removeprefix("user_")
            waveform = waveform_yaml[waveform_key]
            line_number = waveform_yaml.get("line_number", 0)
            waveform = Waveform(waveform=waveform, line_number=line_number, name=name)
            return waveform
        except yaml.YAMLError as e:
            self._handle_yaml_error(e)

    def _handle_yaml_error(self, error):
        # TODO: YAML errors must be displayed in the code editor UI
        self.has_yaml_error = True
