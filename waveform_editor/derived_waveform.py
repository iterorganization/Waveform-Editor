import ast
from typing import Optional

import numpy as np

from waveform_editor.base_waveform import BaseWaveform


class DependencyRenamer(ast.NodeTransformer):
    def __init__(self, rename_from, rename_to, yaml):
        self.rename_from = rename_from
        self.rename_to = rename_to
        self.yaml = yaml

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value == self.rename_from:
            split_yaml = self.yaml.splitlines()
            line_number = node.lineno - 1
            line = split_yaml[line_number]
            split_yaml[line_number] = (
                line[: node.col_offset + 1]
                + self.rename_to
                + line[node.end_col_offset - 1 :]
            )
            self.yaml = "\n".join(split_yaml)
            return ast.copy_location(ast.Constant(value=self.rename_to), node)
        return node


class ExpressionExtractor(ast.NodeTransformer):
    def __init__(self):
        self.string_nodes = []

    def visit_Import(self, node):
        raise ValueError("Import statements are not allowed in waveform expressions.")

    def visit_ImportFrom(self, node):
        raise ValueError("Import statements are not allowed in waveform expressions.")

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.string_nodes.append(node.value)
            return ast.copy_location(ast.Name(id=node.value, ctx=ast.Load()), node)
        return node


class DerivedWaveform(BaseWaveform):
    def __init__(self, yaml_str, name, config, dd_version=None):
        super().__init__(yaml_str, name, dd_version)
        self.config = config
        self.dependent_waveforms = set()
        self.compiled_expr = None
        self.prepare_expression()

    def prepare_expression(self):
        if self.yaml is None:
            return

        try:
            tree = ast.parse(str(self.yaml), mode="eval")
        except Exception as e:
            self.annotations.add(0, f"Could not parse or evaluate the waveform: {e}")
            self.compiled_expr = None
            return

        extractor = ExpressionExtractor()
        modified_tree = extractor.visit(ast.fix_missing_locations(tree))
        self.dependent_waveforms = set(extractor.string_nodes)
        self.compiled_expr = compile(modified_tree, filename="<expr>", mode="eval")

    def rename_dependency(self, old_name, new_name):
        if old_name not in self.dependent_waveforms:
            return

        tree = ast.parse(self.yaml, mode="eval")
        renamer = DependencyRenamer(old_name, new_name, self.yaml)
        ast.fix_missing_locations(renamer.visit(tree))
        self.yaml = renamer.yaml
        self.prepare_expression()

    def _build_eval_context(self, time: np.ndarray) -> dict:
        context = {"np": np}
        for name in self.dependent_waveforms:
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
        result = eval(self.compiled_expr, {"__builtins__": {}}, eval_context)

        # If derived waveform is a constant, ensure an array is returned
        if isinstance(result, (int, float)):
            result = np.full_like(time, result)
        return time, result

    def get_yaml_string(self):
        return str(self.yaml)
