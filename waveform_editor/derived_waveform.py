import ast
from typing import Optional

import numpy as np
from asteval import Interpreter

from waveform_editor.base_waveform import BaseWaveform

NUMPY_UFUNCS = {}
for name in np.__all__:
    obj = getattr(np, name)
    if isinstance(obj, np.ufunc):
        NUMPY_UFUNCS[name] = obj


class DependencyRenamer(ast.NodeTransformer):
    """AST transformer to rename string constants."""

    def __init__(self, rename_from, rename_to, yaml):
        self.rename_from = rename_from
        self.rename_to = rename_to
        self.yaml = yaml

    def visit_Constant(self, node):
        """
        Replace string constants equal to `rename_from` with `rename_to`
        and update the YAML source lines accordingly.
        """
        if isinstance(node.value, str) and node.value == self.rename_from:
            split_yaml = self.yaml.splitlines()
            line_number = node.lineno - 1
            line = split_yaml[line_number]
            split_yaml[line_number] = (
                line[: node.col_offset]
                + line[node.col_offset : node.end_col_offset].replace(
                    self.rename_from, self.rename_to
                )
                + line[node.end_col_offset :]
            )
            self.yaml = "\n".join(split_yaml)
            return ast.copy_location(ast.Constant(value=self.rename_to), node)
        return node


class ExpressionExtractor(ast.NodeTransformer):
    """
    AST transformer extracting all string constants from expressions
    and replacing them with Name nodes for later evaluation.
    """

    def __init__(self):
        self.string_nodes = []

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.string_nodes.append(node.value)
            return ast.copy_location(
                ast.Subscript(
                    value=ast.Name(id="__w", ctx=ast.Load()),
                    slice=ast.Constant(value=node.value),
                    ctx=ast.Load(),
                ),
                node,
            )
        else:
            return node


class DerivedWaveform(BaseWaveform):
    def __init__(self, yaml_str, name, config, dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.config = config
        self.dependencies = set()
        self.is_constant = False
        self.expression = None
        self.prepare_expression()

    def prepare_expression(self):
        """Parse the YAML expression, extract dependencies, transform it for
        evaluation, and compile it.
        """
        if self.yaml is None:
            return

        try:
            tree = ast.parse(str(self.yaml), mode="eval")
        except Exception as e:
            self.annotations.add(0, f"Could not parse or evaluate the waveform: {e}")
            self.expression = None
            return

        extractor = ExpressionExtractor()
        modified_tree = ast.fix_missing_locations(extractor.visit(tree))
        self.is_constant = not extractor.string_nodes
        self.expression = ast.unparse(modified_tree)
        self.dependencies = set(extractor.string_nodes)

    def rename_dependency(self, old_name, new_name):
        """Rename a dependency waveform in the expression.

        Args:
            old_name: Original dependency name.
            new_name: New dependency name.
        """
        if old_name not in self.dependencies:
            return

        tree = ast.parse(self.yaml, mode="eval")
        renamer = DependencyRenamer(old_name, new_name, self.yaml)
        ast.fix_missing_locations(renamer.visit(tree))
        self.yaml = renamer.yaml
        self.prepare_expression()

    def _build_eval_context(self, time: np.ndarray) -> dict:
        """Build the evaluation context dictionary with dependencies resolved.

        Args:
            time: The time array on which to generate points.

        Returns:
            dict: Mapping dependency names to waveform values at given times.
        """
        eval_context = {}

        for name in self.dependencies:
            eval_context[name] = self.config[name].get_value(time)[1]
        return eval_context

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """Evaluate the derived waveform expression at specified times.

        Args:
            time: Array of time points. Defaults to 1000 points between config.start
                and config.end.

        Returns:
            Tuple containing the time and the derived waveform values.
        """
        if time is None:
            # TODO: properly handle time for plotting
            time = np.linspace(self.config.start, self.config.end, 1000)
        if self.expression is None:
            return time, np.zeros_like(time)

        eval_context = self._build_eval_context(time)
        sym_table = NUMPY_UFUNCS.copy()
        sym_table["__w"] = eval_context
        aeval = Interpreter(
            symtable=sym_table,
            minimal=True,
            use_numpy=False,
        )

        # Don't print the entire NumPy array in the error alert message
        with np.printoptions(threshold=10):
            result = aeval.eval(self.expression, raise_errors=True)

        # If derived waveform is a constant, ensure an array is returned
        if self.is_constant:
            return time, np.full_like(time, result)

        # Ensure the result is a 1D array
        if not isinstance(result, np.ndarray):
            raise ValueError("The derived waveform is not a 1D array.")
        result = np.asarray(result)
        if result.shape != time.shape:
            raise ValueError(
                f"The shape of the derived waveform {result.shape} does not match the "
                f"shape of the time array {time.shape}"
            )

        return time, result

    def get_yaml_string(self):
        """Returns the current YAML expression string."""
        return str(self.yaml)
