import ast
from typing import Optional

import numpy as np

from waveform_editor.base_waveform import BaseWaveform


class DependencyRenamer(ast.NodeTransformer):
    def __init__(self, rename_from, rename_to):
        self.rename_from = rename_from
        self.rename_to = rename_to

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value == self.rename_from:
            return ast.copy_location(ast.Constant(value=self.rename_to), node)
        return node


class ExpressionExtractor(ast.NodeTransformer):
    def __init__(self):
        self.string_nodes = []

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.string_nodes.append(node.value)
            return ast.copy_location(ast.Name(id=node.value, ctx=ast.Load()), node)
        return node


class DerivedWaveform(BaseWaveform):
    def __init__(self, yaml_str, name, config, dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.expression = str(self.yaml)
        self.config = config
        self.dependent_waveforms = set()
        self.compiled_expr = None
        self.string_refs = []
        self.prepare_expression()

    def prepare_expression(self):
        if self.yaml is None:
            return

        try:
            tree = ast.parse(self.expression, mode="eval")
        except Exception as e:
            self.annotations.add(0, f"Could not parse or evaluate the waveform: {e}")
            self.compiled_expr = None
            return

        extractor = ExpressionExtractor()
        modified_tree = extractor.visit(ast.fix_missing_locations(tree))
        self.string_refs = extractor.string_nodes

        try:
            self.compiled_expr = compile(modified_tree, filename="<expr>", mode="eval")
        except Exception as e:
            self.annotations.add(0, f"Could not compile the waveform: {e}")
            self.compiled_expr = None
            return

        self.dependent_waveforms = set(self.string_refs)

    def rename_dependency(self, old_name, new_name):
        if old_name not in self.dependent_waveforms:
            return

        tree = ast.parse(self.yaml, mode="eval")
        renamer = DependencyRenamer(rename_from=old_name, rename_to=new_name)
        modified_tree = ast.fix_missing_locations(renamer.visit(tree))

        self.yaml = ast.unparse(modified_tree)
        self.expression = self.yaml
        self.prepare_expression()

    def _build_eval_context(self, time: np.ndarray) -> dict:
        context = {"np": np}
        for name in self.string_refs:
            context[name] = self.config[name].get_value(time)[1]
        return context

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        if time is None:
            # TODO: properly handle time for plotting
            time = np.linspace(self.config.start, self.config.end, 1000)
        if self.compiled_expr is None:
            return time, np.zeros_like(time)

        eval_context = self._build_eval_context(time)
        # WARNING: Using raw eval poses security risks if applied to untrusted input.
        # It can execute arbitrary code, leading to code injection vulnerabilities.
        # Restrict usage strictly to controlled, local, and trusted environments only.
        result = eval(self.compiled_expr, {}, eval_context)

        # If derived waveform is a constant, ensure an array is returned
        if isinstance(result, (int, float)):
            result = np.full_like(time, result)
        return time, result

    def get_yaml_string(self):
        return self.expression
