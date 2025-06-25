import ast
from typing import Optional

import numpy as np

from waveform_editor.annotations import Annotations


class ReplaceStrings(ast.NodeTransformer):
    def __init__(self, derived_waveform, time, eval_context):
        self.eval_context = eval_context
        self.time = time
        self.config = derived_waveform.config
        self.dependent_waveforms = derived_waveform.dependent_waveforms
        self.annotations = derived_waveform.annotations

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            name = node.value
            if name not in self.config.waveform_map:
                self.eval_context[name] = np.zeros_like(self.time)
            else:
                self.eval_context[name] = self.config[name].get_value(self.time)[1]
            self.dependent_waveforms.add(name)
            return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node)
        return node


class DerivedWaveform:
    def __init__(self, waveform=None, name="", config=None):
        self.dependent_waveforms = set()
        self.name = name
        self.tendencies = None
        self.yaml = waveform
        self.config = config
        self.annotations = Annotations()

    def get_value(
        self, time: Optional[np.ndarray] = None
    ) -> tuple[np.ndarray, np.ndarray]:
        if time is None:
            # TODO: handle the time array properly
            time = np.linspace(self.config.start, self.config.end, 1000)
        try:
            tree = ast.parse(self.yaml, mode="eval")
        except SyntaxError as e:
            self.annotations.add(0, f"Expression syntax error: {e}")
            return time, np.zeros_like(time)

        eval_context = {}
        try:
            transformer = ReplaceStrings(self, time, eval_context)
            tree = transformer.visit(tree)
            ast.fix_missing_locations(tree)
            compiled = compile(tree, filename="<expr>", mode="eval")
            result = eval(compiled, {}, eval_context)
        except Exception as e:
            self.annotations.add(0, f"Evaluation error: {e}")
            return time, np.zeros_like(time)

        return time, np.asarray(result)

    def get_derivative(self, time):
        # Derivative not implemented
        return np.zeros_like(time)

    def get_yaml_string(self):
        # TODO: the following is not valid YAML: test/3: 'test/1' + 'test/2'
        # Instead for now encapsulate into string: test/3: "'test/1' + 'test/2'"
        return f'"{self.yaml}"'
