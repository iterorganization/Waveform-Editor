import ast
from typing import Optional

import numpy as np
from ruamel.yaml import YAML

from waveform_editor.annotations import Annotations


class ExpressionTransformer(ast.NodeTransformer):
    def __init__(
        self, rename_from: Optional[str] = None, rename_to: Optional[str] = None
    ):
        self.rename_from = rename_from
        self.rename_to = rename_to
        self.string_nodes = []

    def visit_Constant(self, node):
        if not isinstance(node.value, str):
            return node
        # Rename a specific dependency
        if self.rename_from is not None:
            if node.value == self.rename_from:
                return ast.copy_location(ast.Constant(value=self.rename_to), node)
            return node
        # Prepare expression for evaluation
        else:
            self.string_nodes.append(node.value)
            return ast.copy_location(ast.Name(id=node.value, ctx=ast.Load()), node)


class DerivedWaveform:
    def __init__(self, yaml_str, name, config):
        yaml_dict = YAML().load(yaml_str)
        self.yaml = yaml_dict[name]
        self.expression = str(self.yaml)
        self.tendencies = None
        self.metadata = None
        self.name = name
        self.config = config
        self.annotations = Annotations()
        self.dependent_waveforms = set()
        self.compiled_expr = None
        self.string_refs = []

        self._prepare_expression()

    def _prepare_expression(self):
        if self.yaml is None:
            return
        try:
            tree = ast.parse(self.expression, mode="eval")
            transformer = ExpressionTransformer()
            modified_tree = transformer.visit(ast.fix_missing_locations(tree))
            self.string_refs = transformer.string_nodes
            self.compiled_expr = compile(modified_tree, filename="<expr>", mode="eval")

            self.dependent_waveforms = set()
            for name in self.string_refs:
                self.dependent_waveforms.add(name)

            for dep_name in self.dependent_waveforms:
                if dep_name not in self.config.waveform_map:
                    raise ValueError(f"Undefined dependency: '{dep_name}'")

        except Exception as e:
            self.annotations.add(0, f"Could not parse or evaluate the waveform: {e}")
            self.compiled_expr = None

    def rename_dependency(self, old_name, new_name):
        if self.is_constant or old_name not in self.dependent_waveforms:
            return

        try:
            tree = ast.parse(self.yaml, mode="eval")
            renamer = ExpressionTransformer(rename_from=old_name, rename_to=new_name)
            modified_tree = ast.fix_missing_locations(renamer.visit(tree))

            self.yaml = ast.unparse(modified_tree)
            self._prepare_expression()
        except Exception as e:
            raise RuntimeError(
                f"Failed to rename dependency '{old_name}' to '{new_name}' in "
                f"waveform '{self.name}': {e}"
            ) from e

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
