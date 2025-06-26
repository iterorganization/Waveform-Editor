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

    def rename_node(self, old_name, new_name):
        self.graph[new_name] = self.graph.pop(old_name)

        for dependencies in self.graph.values():
            if old_name in dependencies:
                dependencies.remove(old_name)
                dependencies.add(new_name)

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
