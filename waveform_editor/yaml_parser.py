import re

import yaml

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
    def __init__(self):
        self.waveform = Waveform()

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

            waveform_key = next(
                (
                    key
                    for key in waveform_yaml
                    if key.startswith("user_") and key != "line_number"
                ),
                None,
            )

            waveform = waveform_yaml.get(waveform_key, [])
            line_number = waveform_yaml.get("line_number", 0)
            self.waveform = Waveform(waveform=waveform, line_number=line_number)
        except yaml.YAMLError as e:
            self._handle_yaml_error(e)

        return self.waveform

    def _handle_yaml_error(self, error):
        """Handles YAML parsing errors by adding it to the annotations of the waveform.

        Args:
            error: The YAML error to add to the annotations.
        """
        self.waveform.annotations.clear()
        self.waveform.annotations.add_yaml_error(error)
        self.waveform.tendencies = []
        self.has_yaml_error = True
