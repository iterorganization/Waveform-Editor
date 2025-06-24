from waveform_editor.derived_waveform import DerivedWaveform


class DependencyGraph:
    def __init__(self, waveform_map):
        self.graph = {}
        self._build_graph(waveform_map)

    def _build_graph(self, waveform_map):
        for wf_name, group in waveform_map.items():
            waveform = group.waveforms[wf_name]
            if isinstance(waveform, DerivedWaveform):
                self.graph.setdefault(wf_name, set())
                for dep in waveform.dependent_waveforms:
                    dep_name = dep.name
                    if dep_name in waveform_map:
                        self.graph.setdefault(dep_name, set())
                        self.graph[dep_name].add(wf_name)
        self.detect_cycles()

    def detect_cycles(self):
        visited = set()
        stack = set()

        def visit(node):
            if node in stack:
                raise RuntimeError(f"Cycle detected involving waveform '{node}'")
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            for neighbor in self.graph.get(node, []):
                visit(neighbor)
            stack.remove(node)

        for node in self.graph:
            visit(node)
