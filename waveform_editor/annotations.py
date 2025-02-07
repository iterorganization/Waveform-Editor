import difflib


class Annotations:
    def __init__(self):
        self.annotations = []

    def get(self):
        return self.annotations

    def add_annotations(self, annotations):
        return self.annotations.extend(annotations.get())

    def add(self, line_number, error_msg, is_warning=False):
        """Adds the error message to the list of annotations.

        Args:
            annotations: The list of annotations the error message is added to.
            line_number: The line number at which the error occurs.
            error_msg: The error message the annotation should display.
            error_type: Whether the annotation is a warning. If set to False, it is
                treated as an error.
        """
        error_type = "warning" if is_warning else "error"
        self.annotations.extend(
            [
                {
                    "row": line_number,
                    "column": 0,
                    "text": error_msg,
                    "type": error_type,
                }
            ]
        )

    def add_yaml_error(self, error):
        if hasattr(error, "problem_mark"):
            line = error.problem_mark.line
            # TODO: Is there a way to visualize the column into the annotation?
            # column = error.problem_mark.column
            message = error.problem

            self.add(line, message)
        else:
            self.add(0, f"Unknown YAML error: {error}")

    def create_suggestion(self, match, list):
        suggestion = ""
        close_matches = difflib.get_close_matches(match, list, n=1)
        if close_matches:
            suggestion = f"Did you mean {close_matches[0]!r}?"

        return suggestion

    def clear(self):
        self.annotations.clear()
