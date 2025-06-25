from waveform_editor.derived_waveform import DerivedWaveform


class DependencyGraph:
    def __init__(self, waveform_map):
        self.graph = {}
        self._build_graph(waveform_map)

    def _build_graph(self, waveform_map):
        for name, group in waveform_map.items():
            waveform = group.waveforms[name]
            if isinstance(waveform, DerivedWaveform):
                self.graph.setdefault(name, set())
                for dependent_name in waveform.dependent_waveforms:
                    if dependent_name not in waveform_map:
                        raise ValueError(
                            f"Dependent waveform '{dependent_name}' does not exist."
                        )
                    self.graph.setdefault(dependent_name, set())
                    self.graph[dependent_name].add(name)
        self.detect_cycles()

    def detect_cycles(self):
        visited = set()
        stack = set()
        for node in self.graph:
            self._visit(node, visited, stack)

    def _visit(self, node, visited, stack):
        if node in stack:
            raise RuntimeError(
                f"Circular dependency detected involving waveform '{node}'"
            )
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        for neighbor in self.graph.get(node, []):
            self._visit(neighbor, visited, stack)
        stack.remove(node)
