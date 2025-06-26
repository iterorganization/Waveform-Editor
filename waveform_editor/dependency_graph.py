class DependencyGraph:
    def __init__(self):
        self.graph = {}

    def add_node(self, name, dependencies):
        self.graph[name] = set(dependencies)
        self.detect_cycles()

    def remove_node(self, name):
        if name in self.graph:
            del self.graph[name]
        for deps in self.graph.values():
            deps.discard(name)

    def detect_cycles(self):
        visited = set()
        stack = set()
        for node in self.graph:
            self._visit(node, visited, stack)

    def _visit(self, node, visited, stack):
        if node in stack:
            raise RuntimeError(f"Circular dependency detected involving '{node}'")
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        for neighbor in self.graph.get(node, []):
            self._visit(neighbor, visited, stack)
        stack.remove(node)

    def print(self):
        for node, deps in self.graph.items():
            if deps:
                print(f"{node} -> {', '.join(deps)}")
            else:
                print(f"{node} -> (no dependencies)")
