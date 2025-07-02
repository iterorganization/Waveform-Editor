class DependencyGraph:
    """
    Manages dependencies between nodes (e.g., waveforms) and enforces acyclic
    constraints.
    """

    def __init__(self):
        self.graph = {}

    def __contains__(self, name):
        return name in self.graph

    def check_safe_to_remove(self, name):
        """Verify that a node can be removed without breaking dependencies.

        Args:
            name: Node name to check.
        """
        for node, deps in self.graph.items():
            if name in deps:
                raise RuntimeError(
                    f"Cannot remove waveform {name!r} because it is a dependency of "
                    f"{node!r}"
                )

    def check_safe_to_replace(self, name, dependencies):
        """Check if replacing a node's dependencies would introduce cycles.

        Args:
            name: Node name to check.
            dependencies: Set of new dependencies for the node.
        """
        if name not in self.graph:
            return
        old_deps = self.graph[name]
        self.graph[name] = set(dependencies)
        try:
            self.detect_cycles()
        finally:
            self.graph[name] = old_deps

    def replace_node(self, name, dependencies):
        """Replace the dependencies of an existing node or add it if missing.

        Args:
            name: The name of the node.
            dependencies: Set of new dependencies for the node.
        """
        if name not in self.graph:
            self.add_node(name, dependencies)
            return
        old = self.graph[name]
        self.graph[name] = set(dependencies)
        try:
            self.detect_cycles()
        except RuntimeError:
            self.graph[name] = old
            raise

    def add_node(self, name, dependencies):
        """Add a new node with specified dependencies. Validates that there are no
        cycles and removes node on failure.

        Args:
            name: The name of the node.
            dependencies: Set of new dependencies for the node.
        """
        self.graph[name] = set(dependencies)
        try:
            self.detect_cycles()
        except RuntimeError:
            del self.graph[name]
            raise

    def remove_node(self, name):
        """Remove a node from the graph.

        Args:
            name: Node name to remove.
        """
        del self.graph[name]

    def rename_node(self, old_name, new_name):
        """Rename a node and update all dependencies referencing it.

        Args:
            old_name: Name of the existing node.
            new_name: New node name.

        Returns:
            Names of nodes that depended on the renamed node.
        """
        dependents = [node for node, deps in self.graph.items() if old_name in deps]

        if old_name in self.graph:
            self.graph[new_name] = self.graph.pop(old_name)

        for dependent_name in dependents:
            dependencies = self.graph[dependent_name]
            dependencies.remove(old_name)
            dependencies.add(new_name)
        return dependents

    def detect_cycles(self, start_node=None):
        """Detect cycles in the graph, optionally starting from a specific node. Raises
        RuntimeError if a circular dependency is found.

        Args:
            start_node: Node to start detection from. Checks entire graph if None.
        """
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
