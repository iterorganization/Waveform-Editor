import difflib
from collections import UserList


class Annotations(UserList):
    def __str__(self):
        sorted_annotations = sorted(self, key=lambda ann: ann["row"])
        return "\n".join(
            f"Line {a['row'] + 1}: {a['text']}" for a in sorted_annotations
        )

    def add_annotations(self, annotations):
        """Merge another Annotations instance into this instance by appending its
        annotations.

        Args:
            annotations: The Annotations object to append.
        """
        return self.extend(annotations)

    def add(self, line_number, error_msg, is_warning=False):
        """Adds the error message to the list of annotations.

        Args:
            line_number: The line number at which the error occurs.
            error_msg: The error message the annotation should display.
            is_warning: Whether the annotation is a warning. If set to False, it is
                treated as an error.
        """
        error_type = "warning" if is_warning else "error"
        # The key of the kv-pair is removed in the editor, so we account for this
        if line_number > 0:
            line_number -= 1
        self.append(
            {
                "row": line_number,
                "column": 0,
                "text": error_msg,
                "type": error_type,
            }
        )

    def add_yaml_error(self, error):
        """Add a YAML parsing error to the annotations.

        Args:
            error: The YAML parsing error to be added as annotations.
        """
        message = "Unable to parse the YAML file:\n"
        if hasattr(error, "problem_mark"):
            line = error.problem_mark.line
            # TODO: Is there a way to visualize the column into the annotation? They are
            # currently ignored.
            # column = error.problem_mark.column
            message += f"{error.problem}"
        else:
            line = 0
            message += f"{error}"
        self.add(line, message)

    def suggest(self, word_to_match, possible_matches):
        """Suggest a close match for a given word from a list of possible matches.

        Args:
            word_to_match: The word for which a suggestion is needed.
            possible_matches: A list of possible correct words.
        """
        suggestion = ""
        close_matches = difflib.get_close_matches(word_to_match, possible_matches, n=1)
        if close_matches:
            suggestion = f"Did you mean {close_matches[0]!r}?\n"

        return suggestion
