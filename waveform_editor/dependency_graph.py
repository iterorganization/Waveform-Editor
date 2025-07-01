from waveform_editor.derived_waveform import DerivedWaveform


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

    def rename_node(self, old_name, new_name, config):
        dependents = {node for node, deps in self.graph.items() if old_name in deps}
        for dependent_name in dependents:
            dependent_waveform = config[dependent_name]
            if isinstance(dependent_waveform, DerivedWaveform):
                dependent_waveform.rename_dependency(old_name, new_name)

        if old_name in self.graph:
            self.graph[new_name] = self.graph.pop(old_name)

        for dependencies in self.graph.values():
            if old_name in dependencies:
                dependencies.remove(old_name)
                dependencies.add(new_name)

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

    def print(self):
        for node, deps in self.graph.items():
            if deps:
                print(f"{node} -> {', '.join(deps)}")
            else:
                print(f"{node} -> (no dependencies)")
