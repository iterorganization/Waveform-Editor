import ast

import numpy as np
from asteval import Interpreter

from waveform_editor.tendencies.base import BaseTendency

NUMPY_UFUNCS = {}
for _name in np.__all__:
    _obj = getattr(np, _name)
    if isinstance(_obj, np.ufunc):
        NUMPY_UFUNCS[_name] = _obj


class DependencyRenamer(ast.NodeTransformer):
    """AST transformer to rename a string constant (a waveform reference)."""

    def __init__(self, rename_from, rename_to, source):
        self.rename_from = rename_from
        self.rename_to = rename_to
        self.source = source

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value == self.rename_from:
            lines = self.source.splitlines()
            i = node.lineno - 1
            line = lines[i]
            lines[i] = (
                line[: node.col_offset]
                + line[node.col_offset : node.end_col_offset].replace(
                    self.rename_from, self.rename_to
                )
                + line[node.end_col_offset :]
            )
            self.source = "\n".join(lines)
            return ast.copy_location(ast.Constant(value=self.rename_to), node)
        return node


class ExpressionExtractor(ast.NodeTransformer):
    """Replace string constants (waveform references) with ``__w[...]`` lookups."""

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
        return node


class ExpressionTendency(BaseTendency):
    """A tendency whose values are computed from an expression over other waveforms.

    References to other waveforms are written as quoted strings (e.g. ``"a" * 10``).
    Without any references the expression is a constant. The owning waveform resolves
    dependencies through the configuration passed in ``config``.
    """

    def __init__(self, user_expression=None, config=None, **kwargs):
        self.config = config
        self.source = user_expression
        self.dependencies = set()
        self.is_constant = False
        self.expression = None
        super().__init__(**kwargs)
        self.prepare_expression()

    def prepare_expression(self):
        """Parse the expression, extract dependencies and compile it for evaluation."""
        if self.source is None:
            return
        try:
            tree = ast.parse(str(self.source), mode="eval")
        except Exception as e:
            self.annotations.add(self.line_number, f"Could not parse expression: {e}")
            self.expression = None
            return
        extractor = ExpressionExtractor()
        modified = ast.fix_missing_locations(extractor.visit(tree))
        self.is_constant = not extractor.string_nodes
        self.expression = ast.unparse(modified)
        self.dependencies = set(extractor.string_nodes)

    def rename_dependency(self, old_name, new_name):
        if old_name not in self.dependencies:
            return
        tree = ast.parse(str(self.source), mode="eval")
        renamer = DependencyRenamer(old_name, new_name, str(self.source))
        ast.fix_missing_locations(renamer.visit(tree))
        self.source = renamer.source
        self.prepare_expression()

    def _calc_start_end_values(self):
        # Boundary values depend on the configuration and dependencies, which are not
        # resolvable at construction time, so they are not computed eagerly.
        pass

    def get_value(self, time: np.ndarray | None = None):
        if time is None:
            time = np.linspace(self.config.start, self.config.end, 1000)
        if self.expression is None:
            return time, np.zeros_like(time)

        eval_context = {
            name: self.config[name].get_value(time)[1] for name in self.dependencies
        }
        sym_table = NUMPY_UFUNCS.copy()
        sym_table["__w"] = eval_context
        aeval = Interpreter(symtable=sym_table, minimal=True, use_numpy=False)

        with np.printoptions(threshold=10):
            result = aeval.eval(self.expression, raise_errors=True)

        if self.is_constant:
            return time, np.full_like(time, result, dtype=float)

        result = np.asarray(result)
        if result.shape != time.shape:
            raise ValueError(
                f"The shape of the derived waveform {result.shape} does not match the "
                f"shape of the time array {time.shape}"
            )
        return time, result

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        return np.zeros_like(time, dtype=float)
