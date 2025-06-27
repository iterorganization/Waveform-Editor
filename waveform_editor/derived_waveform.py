import ast
from typing import Optional

import numpy as np

from waveform_editor.annotations import Annotations


class ReplaceStrings(ast.NodeTransformer):
    def __init__(self):
        self.string_nodes = []

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.string_nodes.append(node.value)
            return ast.copy_location(ast.Name(id=node.value, ctx=ast.Load()), node)
        return node


class DerivedWaveform:
    def __init__(self, waveform=None, name="", config=None):
        self.name = name
        self.yaml = waveform
        self.config = config
        self.annotations = Annotations()
        self.dependent_waveforms = set()
        self.compiled_expr = None
        self.string_refs = []

        if isinstance(waveform, str):
            self.is_constant = False
        else:
            self.is_constant = True
            self.yaml = str(self.yaml)
        self._prepare_expression()

    def _prepare_expression(self):
        if self.yaml is None:
            return
        try:
            expression = str(self.yaml) if self.is_constant else self.yaml
            tree = ast.parse(expression, mode="eval")
            transformer = ReplaceStrings()
            modified_tree = transformer.visit(ast.fix_missing_locations(tree))
            self.string_refs = transformer.string_nodes
            self.compiled_expr = compile(modified_tree, filename="<expr>", mode="eval")

            for name in self.string_refs:
                self.dependent_waveforms.add(name)

        except Exception as e:
            self.annotations.add(0, f"Could not parse or evaluate the waveform: {e}")
            self.compiled_expr = None

    def _build_eval_context(self, time: np.ndarray) -> dict:
        context = {"np": np}
        for name in self.string_refs:
            if name not in self.config.waveform_map:
                context[name] = np.zeros_like(time)
            else:
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
        result = eval(self.compiled_expr, {}, eval_context)

        # If derived waveform is a constant, ensure an array is returned
        if isinstance(result, (int, float)):
            result = np.full_like(time, result)
        return time, result

    def get_derivative(self, time):
        # Derivative not implemented
        return np.zeros_like(time)

    def get_yaml_string(self):
        if self.is_constant:
            return self.yaml
        else:
            return f'"{self.yaml}"'
