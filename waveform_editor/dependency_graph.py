class DependencyGraph:
    def __init__(self):
        self.graph = {}

    def __contains__(self, name):
        return name in self.graph

    def check_safe_to_remove(self, name):
        for node, deps in self.graph.items():
            if name in deps:
                raise RuntimeError(
                    f"Cannot remove waveform {name!r} because it is a dependency of "
                    f"{node!r}"
                )

    def check_safe_to_replace(self, name, dependencies):
        if name not in self.graph:
            return
        old_deps = self.graph[name]
        self.graph[name] = set(dependencies)
        try:
            self.detect_cycles()
        finally:
            self.graph[name] = old_deps

    def replace_node(self, name, dependencies):
        old = self.graph[name]
        self.graph[name] = set(dependencies)
        try:
            self.detect_cycles()
        except RuntimeError:
            self.graph[name] = old
            raise

    def add_node(self, name, dependencies):
        self.graph[name] = set(dependencies)
        try:
            self.detect_cycles()
        except RuntimeError:
            del self.graph[name]
            raise

    def remove_node(self, name):
        if name not in self.graph:
            raise ValueError(f"{name} does not exist in the dependency graph.")
        del self.graph[name]

    def rename_node(self, old_name, new_name):
        dependents = [node for node, deps in self.graph.items() if old_name in deps]

        if old_name in self.graph:
            self.graph[new_name] = self.graph.pop(old_name)

        for dependent_name in dependents:
            dependencies = self.graph[dependent_name]
            dependencies.remove(old_name)
            dependencies.add(new_name)
        return dependents

    def detect_cycles(self, start_node=None):
        visited = set()
        stack = set()

        def visit(node):
            if node in stack:
                raise RuntimeError(f"Circular dependency detected involving '{node}'")
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            for neighbor in self.graph.get(node, []):
                visit(neighbor)
            stack.remove(node)

        if start_node is not None:
            if start_node not in self.graph:
                return
            visit(start_node)
        else:
            for node in self.graph:
                visit(node)
