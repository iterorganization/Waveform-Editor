class DependencyGraph:
    def __init__(self):
        self.graph = {}

    def add_node(self, name, dependencies, check_cycle=True):
        self.graph.setdefault(name, set())
        for node in list(self.graph.keys()):
            self.graph[node].discard(name)
        for dep in dependencies:
            self.graph.setdefault(dep, set()).add(name)
        if check_cycle:
            self.detect_cycles()

    def remove_node(self, name):
        if name in self.graph:
            del self.graph[name]
        for node in self.graph:
            self.graph[node].discard(name)

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
