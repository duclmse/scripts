"""
Deps Command - Visualize and analyze resource dependencies
"""

import json
from collections import defaultdict
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors


@Command.register("deps", help="Show resource dependencies", args=[
    arg("resource_type", nargs="?",
        help="Resource type (deployment, service, pod, etc)"),
    arg("resource_name", nargs="?", help="Specific resource name"),

    # Display options
    arg("-o", "--output", choices=["tree", "graph", "json", "dot", "mermaid"],
        default="tree", help="Output format"),
    arg("--direction", choices=["forward", "reverse", "both"], default="forward",
        help="Show dependencies (forward), dependents (reverse), or both"),
    arg("--depth", type=int, help="Maximum depth to traverse"),
    arg("--show-labels", action="store_true", help="Show labels in output"),
    arg("--show-annotations", action="store_true", help="Show annotations"),

    # Filtering
    arg("-l", "--selector", help="Label selector"),
    arg("--types", help="Resource types to include (comma-separated)"),
    arg("--exclude-types", help="Resource types to exclude"),
    arg("--include-external", action="store_true",
        help="Include external dependencies (configmaps, secrets)"),

    # Analysis options
    arg("--find-cycles", action="store_true",
        help="Find circular dependencies"),
    arg("--find-orphans", action="store_true", help="Find orphaned resources"),
    arg("--impact-analysis", help="Show impact of deleting this resource"),
    arg("--critical-path", action="store_true", help="Highlight critical path"),

    # Export
    arg("--export", help="Export to file"),
    arg("--format-output", action="store_true",
        help="Format output (for dot/mermaid)"),
])
class DepsCommand:
    """Visualize and analyze resource dependencies"""

    def __init__(self, kube):
        self.kube = kube
        self.resources = {}
        self.dependencies = defaultdict(set)
        self.dependents = defaultdict(set)
        self.resource_cache = {}

    def execute(self, args):
        """Execute dependency analysis"""
        Logger.info("Analyzing dependencies...")

        # Fetch all resources
        self.fetch_all_resources(args)

        # Build dependency graph
        self.build_dependency_graph(args)

        # Perform analysis
        if args.find_cycles:
            self.find_cycles()
        elif args.find_orphans:
            self.find_orphans()
        elif args.impact_analysis:
            self.impact_analysis(args.impact_analysis)
        else:
            # Display dependencies
            if args.resource_type and args.resource_name:
                self.show_resource_deps(
                    args.resource_type, args.resource_name, args)
            else:
                self.show_all_deps(args)

        # Export if requested
        if args.export:
            self.export_graph(args.export, args.output)

    def fetch_all_resources(self, args):
        """Fetch all resources from cluster"""
        resource_types = [
            "pods", "deployments", "replicasets", "statefulsets", "daemonsets",
            "services", "ingresses", "configmaps", "secrets", "persistentvolumeclaims",
            "jobs", "cronjobs"
        ]

        if args.types:
            resource_types = args.types.split(',')

        if args.exclude_types:
            exclude = args.exclude_types.split(',')
            resource_types = [rt for rt in resource_types if rt not in exclude]

        for rtype in resource_types:
            Logger.verbose_log(f"Fetching {rtype}...")

            cmd = ["get", rtype, "-n", self.kube.namespace, "-o", "json"]

            if args.selector:
                cmd.extend(["-l", args.selector])

            try:
                result = self.kube.run(cmd, check=False)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    items = data.get('items', [])

                    for item in items:
                        key = self.get_resource_key(item)
                        self.resource_cache[key] = item

            except Exception as e:
                Logger.warn(f"Failed to fetch {rtype}: {e}")

    def get_resource_key(self, resource: dict) -> str:
        """Get unique key for resource"""
        kind = resource.get('kind', 'Unknown')
        name = resource['metadata']['name']
        return f"{kind}/{name}"

    def build_dependency_graph(self, args):
        """Build dependency graph from resources"""
        for key, resource in self.resource_cache.items():
            kind = resource.get('kind')

            # Find dependencies based on resource type
            if kind == "Deployment":
                self.analyze_deployment(key, resource, args)
            elif kind == "Pod":
                self.analyze_pod(key, resource, args)
            elif kind == "Service":
                self.analyze_service(key, resource, args)
            elif kind == "Ingress":
                self.analyze_ingress(key, resource, args)
            elif kind == "StatefulSet":
                self.analyze_statefulset(key, resource, args)
            elif kind == "Job":
                self.analyze_job(key, resource, args)

    def analyze_deployment(self, key: str, resource: dict, args):
        """Analyze deployment dependencies"""
        spec = resource.get('spec', {})
        template = spec.get('template', {})

        # ReplicaSets (owned)
        owner_refs = resource.get('metadata', {}).get('ownerReferences', [])
        for owner in owner_refs:
            owner_key = f"{owner['kind']}/{owner['name']}"
            self.add_dependency(key, owner_key)

        # ConfigMaps and Secrets
        if args.include_external:
            self.find_configmap_secret_deps(key, template, args)

        # Services (labels)
        self.find_service_deps(key, spec.get(
            'selector', {}).get('matchLabels', {}))

        # PVCs
        self.find_pvc_deps(key, template)

    def analyze_pod(self, key: str, resource: dict, args):
        """Analyze pod dependencies"""
        spec = resource.get('spec', {})

        # Owner references (Deployment, ReplicaSet, etc.)
        owner_refs = resource.get('metadata', {}).get('ownerReferences', [])
        for owner in owner_refs:
            owner_key = f"{owner['kind']}/{owner['name']}"
            self.add_dependency(key, owner_key)

        # ConfigMaps and Secrets
        if args.include_external:
            self.find_configmap_secret_deps(key, {"spec": spec}, args)

        # PVCs
        self.find_pvc_deps(key, {"spec": spec})

    def analyze_service(self, key: str, resource: dict, args):
        """Analyze service dependencies"""
        spec = resource.get('spec', {})
        selector = spec.get('selector', {})

        # Find pods matching selector
        for res_key, res in self.resource_cache.items():
            if res.get('kind') == 'Pod':
                pod_labels = res.get('metadata', {}).get('labels', {})
                if self.labels_match(selector, pod_labels):
                    self.add_dependency(key, res_key)

    def analyze_ingress(self, key: str, resource: dict, args):
        """Analyze ingress dependencies"""
        spec = resource.get('spec', {})

        # Find backend services
        rules = spec.get('rules', [])
        for rule in rules:
            http = rule.get('http', {})
            paths = http.get('paths', [])
            for path in paths:
                backend = path.get('backend', {})
                service = backend.get('service', {})
                service_name = service.get('name')

                if service_name:
                    service_key = f"Service/{service_name}"
                    self.add_dependency(key, service_key)

        # Default backend
        default_backend = spec.get('defaultBackend', {})
        if default_backend:
            service = default_backend.get('service', {})
            service_name = service.get('name')
            if service_name:
                service_key = f"Service/{service_name}"
                self.add_dependency(key, service_key)

    def analyze_statefulset(self, key: str, resource: dict, args):
        """Analyze statefulset dependencies"""
        # Similar to deployment
        self.analyze_deployment(key, resource, args)

    def analyze_job(self, key: str, resource: dict, args):
        """Analyze job dependencies"""
        spec = resource.get('spec', {})
        template = spec.get('template', {})

        # ConfigMaps and Secrets
        if args.include_external:
            self.find_configmap_secret_deps(key, template, args)

    def find_configmap_secret_deps(self, key: str, template: dict, args):
        """Find ConfigMap and Secret dependencies"""
        spec = template.get('spec', {})
        containers = spec.get('containers', [])

        for container in containers:
            # Env from ConfigMap/Secret
            env_from = container.get('envFrom', [])
            for env in env_from:
                if 'configMapRef' in env:
                    cm_name = env['configMapRef']['name']
                    self.add_dependency(key, f"ConfigMap/{cm_name}")
                if 'secretRef' in env:
                    secret_name = env['secretRef']['name']
                    self.add_dependency(key, f"Secret/{secret_name}")

            # Env from specific keys
            env_vars = container.get('env', [])
            for env in env_vars:
                value_from = env.get('valueFrom', {})
                if 'configMapKeyRef' in value_from:
                    cm_name = value_from['configMapKeyRef']['name']
                    self.add_dependency(key, f"ConfigMap/{cm_name}")
                if 'secretKeyRef' in value_from:
                    secret_name = value_from['secretKeyRef']['name']
                    self.add_dependency(key, f"Secret/{secret_name}")

        # Volume mounts
        volumes = spec.get('volumes', [])
        for volume in volumes:
            if 'configMap' in volume:
                cm_name = volume['configMap']['name']
                self.add_dependency(key, f"ConfigMap/{cm_name}")
            if 'secret' in volume:
                secret_name = volume['secret']['secretName']
                self.add_dependency(key, f"Secret/{secret_name}")

    def find_service_deps(self, key: str, labels: dict):
        """Find services matching labels"""
        for res_key, res in self.resource_cache.items():
            if res.get('kind') == 'Service':
                selector = res.get('spec', {}).get('selector', {})
                if self.labels_match(selector, labels):
                    self.add_dependency(res_key, key)

    def find_pvc_deps(self, key: str, template: dict):
        """Find PVC dependencies"""
        spec = template.get('spec', {})
        volumes = spec.get('volumes', [])

        for volume in volumes:
            if 'persistentVolumeClaim' in volume:
                pvc_name = volume['persistentVolumeClaim']['claimName']
                self.add_dependency(key, f"PersistentVolumeClaim/{pvc_name}")

    def labels_match(self, selector: dict, labels: dict) -> bool:
        """Check if labels match selector"""
        if not selector:
            return False

        for key, value in selector.items():
            if labels.get(key) != value:
                return False

        return True

    def add_dependency(self, source: str, target: str):
        """Add dependency relationship"""
        if target in self.resource_cache or '/' in target:
            self.dependencies[source].add(target)
            self.dependents[target].add(source)

    def show_resource_deps(self, rtype: str, name: str, args):
        """Show dependencies for specific resource"""
        key = f"{rtype.capitalize()}/{name}"

        if key not in self.resource_cache and key not in self.dependencies and key not in self.dependents:
            Logger.error(f"Resource not found: {key}")
            return

        print(f"\n{Colors.BOLD}Dependencies for {key}{Colors.RESET}")
        print("=" * 60)

        if args.direction in ["forward", "both"]:
            print(f"\n{Colors.GREEN}Depends on:{Colors.RESET}")
            self.print_tree(key, self.dependencies, depth=args.depth or 10)

        if args.direction in ["reverse", "both"]:
            print(f"\n{Colors.YELLOW}Used by:{Colors.RESET}")
            self.print_tree(key, self.dependents, depth=args.depth or 10)

    def show_all_deps(self, args):
        """Show all dependencies"""
        if args.output == "tree":
            self.display_tree(args)
        elif args.output == "graph":
            self.display_graph(args)
        elif args.output == "json":
            self.display_json(args)
        elif args.output == "dot":
            self.display_dot(args)
        elif args.output == "mermaid":
            self.display_mermaid(args)

    def print_tree(self, key: str, graph: dict[str, set],
                   visited: set | None = None, depth: int = 10, level: int = 0, prefix: str = ""):
        """Print dependency tree"""
        if visited is None:
            visited = set()

        if key in visited or level >= depth:
            return

        visited.add(key)
        deps = graph.get(key, set())

        for i, dep in enumerate(sorted(deps)):
            is_last = i == len(deps) - 1
            connector = "└─" if is_last else "├─"

            # Color by type
            dep_type = dep.split('/')[0]
            color = self.get_type_color(dep_type)

            print(f"{prefix}{connector} {color}{dep}{Colors.RESET}")

            # Recurse
            new_prefix = prefix + ("   " if is_last else "│  ")
            self.print_tree(dep, graph, visited, depth, level + 1, new_prefix)

    def display_tree(self, args):
        """Display as tree"""
        print(f"\n{Colors.BOLD}Resource Dependency Tree{Colors.RESET}")
        print("=" * 60)

        # Find root resources (no dependents or specified)
        roots = []
        for key in self.resource_cache.keys():
            if not self.dependents.get(key):
                roots.append(key)

        if not roots:
            roots = list(self.resource_cache.keys())[:10]

        for root in sorted(roots):
            color = self.get_type_color(root.split('/')[0])
            print(f"\n{color}{Colors.BOLD}{root}{Colors.RESET}")
            self.print_tree(root, self.dependencies, depth=args.depth or 3)

    def display_graph(self, args):
        """Display as ASCII graph"""
        print(f"\n{Colors.BOLD}Resource Dependency Graph{Colors.RESET}")
        print("=" * 60)

        for source, targets in sorted(self.dependencies.items()):
            if targets:
                src_color = self.get_type_color(source.split('/')[0])
                print(f"\n{src_color}{source}{Colors.RESET}")

                for target in sorted(targets):
                    tgt_color = self.get_type_color(target.split('/')[0])
                    print(f"  └─> {tgt_color}{target}{Colors.RESET}")

    def display_json(self, args):
        """Display as JSON"""
        output = {
            'resources': list(self.resource_cache.keys()),
            'dependencies': {k: list(v) for k, v in self.dependencies.items()},
            'dependents': {k: list(v) for k, v in self.dependents.items()}
        }
        print(json.dumps(output, indent=2))

    def display_dot(self, args):
        """Display as Graphviz DOT format"""
        print("digraph Dependencies {")
        print("  rankdir=LR;")
        print("  node [shape=box];")
        print()

        # Add nodes with colors
        for key in self.resource_cache.keys():
            rtype = key.split('/')[0]
            color = self.get_dot_color(rtype)
            label = key.split('/')[-1]
            print(
                f'  "{key}" [label="{label}\\n({rtype})", fillcolor="{color}", style=filled];')

        print()

        # Add edges
        for source, targets in self.dependencies.items():
            for target in targets:
                print(f'  "{source}" -> "{target}";')

        print("}")

        if args.format_output:
            print(f"\n{Colors.YELLOW}# Generate image with:{Colors.RESET}")
            print(f"  dot -Tpng output.dot -o dependencies.png")

    def display_mermaid(self, args):
        """Display as Mermaid diagram"""
        print("graph TD")

        # Create node IDs (alphanumeric only)
        node_ids = {}
        counter = 0
        for key in self.resource_cache.keys():
            node_ids[key] = f"N{counter}"
            counter += 1

        # Add nodes
        for key, node_id in node_ids.items():
            rtype, name = key.split('/', 1)
            print(f"  {node_id}[\"{name}<br/>({rtype})\"]")

        # Add edges
        for source, targets in self.dependencies.items():
            if source in node_ids:
                for target in targets:
                    if target in node_ids:
                        print(f"  {node_ids[source]} --> {node_ids[target]}")

        if args.format_output:
            print(
                f"\n{Colors.YELLOW}# Paste into https://mermaid.live{Colors.RESET}")

    def find_cycles(self):
        """Find circular dependencies"""
        print(f"\n{Colors.BOLD}Checking for circular dependencies...{Colors.RESET}")

        cycles = []
        visited = set()
        rec_stack = []

        def dfs(node, path):
            if node in rec_stack:
                cycle_start = rec_stack.index(node)
                cycle = rec_stack[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.append(node)

            for dep in self.dependencies.get(node, []):
                dfs(dep, path + [dep])

            rec_stack.pop()

        for node in self.resource_cache.keys():
            if node not in visited:
                dfs(node, [node])

        if cycles:
            print(
                f"\n{Colors.RED}Found {len(cycles)} circular dependency(ies):{Colors.RESET}")
            for cycle in cycles:
                print(f"  {' -> '.join(cycle)}")
        else:
            Logger.success("No circular dependencies found")

    def find_orphans(self):
        """Find orphaned resources"""
        print(f"\n{Colors.BOLD}Finding orphaned resources...{Colors.RESET}")

        orphans = []
        for key in self.resource_cache.keys():
            # Check if has no dependents and is not a base resource
            if not self.dependents.get(key) and not self.dependencies.get(key):
                orphans.append(key)

        if orphans:
            print(
                f"\n{Colors.YELLOW}Found {len(orphans)} orphaned resource(s):{Colors.RESET}")
            for orphan in sorted(orphans):
                print(f"  • {orphan}")
        else:
            Logger.success("No orphaned resources found")

    def impact_analysis(self, resource_name: str):
        """Analyze impact of deleting a resource"""
        # Try to find the resource
        matching = [k for k in self.resource_cache.keys()
                    if resource_name in k]

        if not matching:
            Logger.error(f"Resource not found: {resource_name}")
            return

        key = matching[0]

        print(f"\n{Colors.BOLD}Impact Analysis for {key}{Colors.RESET}")
        print("=" * 60)

        # Find all dependent resources
        affected = set()

        def find_affected(node, visited=None):
            if visited is None:
                visited = set()

            if node in visited:
                return

            visited.add(node)
            affected.add(node)

            for dependent in self.dependents.get(node, []):
                find_affected(dependent, visited)

        find_affected(key)
        affected.remove(key)  # Remove self

        if affected:
            print(
                f"\n{Colors.RED}Deleting this will affect {len(affected)} resource(s):{Colors.RESET}")
            for res in sorted(affected):
                print(f"  • {res}")
        else:
            Logger.success("No other resources will be affected")

    def get_type_color(self, rtype: str) -> str:
        """Get color for resource type"""
        colors = {
            'Deployment': Colors.GREEN,
            'Service': Colors.BLUE,
            'Pod': Colors.CYAN,
            'Ingress': Colors.MAGENTA,
            'ConfigMap': Colors.YELLOW,
            'Secret': Colors.RED,
            'PersistentVolumeClaim': Colors.MAGENTA,
        }
        return colors.get(rtype, Colors.RESET)

    def get_dot_color(self, rtype: str) -> str:
        """Get color for DOT format"""
        colors = {
            'Deployment': 'lightgreen',
            'Service': 'lightblue',
            'Pod': 'lightyellow',
            'Ingress': 'pink',
            'ConfigMap': 'wheat',
            'Secret': 'lightcoral',
        }
        return colors.get(rtype, 'white')

    def export_graph(self, filepath: str, format: str):
        """Export graph to file"""
        from pathlib import Path

        if format == "json":
            output = {
                'dependencies': {k: list(v) for k, v in self.dependencies.items()},
                'dependents': {k: list(v) for k, v in self.dependents.items()}
            }
            Path(filepath).write_text(json.dumps(output, indent=2))
        elif format == "dot":
            # Redirect stdout to capture dot output
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            self.display_dot(type('Args', (), {'format_output': False})())
            content = sys.stdout.getvalue()
            sys.stdout = old_stdout
            Path(filepath).write_text(content)

        Logger.success(f"Exported to {filepath}")


# Usage examples
"""
# Show all dependencies as tree
python k8s-mgr.py deps

# Show dependencies for specific deployment
python k8s-mgr.py deps deployment backend

# Show what depends on a service (reverse)
python k8s-mgr.py deps service api --direction=reverse

# Show both forward and reverse dependencies
python k8s-mgr.py deps deployment backend --direction=both

# Include ConfigMaps and Secrets
python k8s-mgr.py deps --include-external

# Find circular dependencies
python k8s-mgr.py deps --find-cycles

# Find orphaned resources
python k8s-mgr.py deps --find-orphans

# Impact analysis (what breaks if I delete this?)
python k8s-mgr.py deps --impact-analysis=backend-deployment

# Export as Graphviz DOT
python k8s-mgr.py deps -o dot --export=deps.dot

# Export as Mermaid diagram
python k8s-mgr.py deps -o mermaid --export=deps.mmd

# JSON export
python k8s-mgr.py deps -o json --export=deps.json

# Limit depth
python k8s-mgr.py deps deployment backend --depth=2

# Filter by resource types
python k8s-mgr.py deps --types=deployments,services,ingresses

# Exclude certain types
python k8s-mgr.py deps --exclude-types=pods,replicasets

# With label selector
python k8s-mgr.py deps -l app=backend
"""
