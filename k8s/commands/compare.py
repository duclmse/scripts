"""
Compare Command - Compare resources across environments/contexts
"""

import json
import yaml
import difflib
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors
from utils.formatters import format_table


@Command.register("compare", help="Compare resources across contexts/namespaces", args=[
    arg("resource_type",
        help="Resource type to compare (deployment, service, configmap, etc)"),
    arg("resource_name", nargs="?", help="Specific resource name (optional)"),

    # Comparison targets
    arg("--contexts", help="Comma-separated contexts to compare (e.g., dev,staging,prod)"),
    arg("--namespaces", help="Comma-separated namespaces to compare"),
    arg("--from-context", help="Source context"),
    arg("--to-context", help="Target context"),
    arg("--from-namespace", help="Source namespace"),
    arg("--to-namespace", help="Target namespace"),

    # Comparison options
    arg("--fields", help="Specific fields to compare (comma-separated)"),
    arg("--ignore-fields", help="Fields to ignore (comma-separated)"),
    arg("--ignore-metadata", action="store_true",
        help="Ignore metadata differences"),
    arg("--ignore-status", action="store_true",
        help="Ignore status differences"),
    arg("--show-all", action="store_true",
        help="Show all resources, not just different ones"),

    # Output options
    arg("-o", "--output", choices=["table", "yaml", "json", "diff"],
        default="table", help="Output format"),
    arg("--diff-context", type=int, default=3, help="Lines of context in diff"),
    arg("--color-diff", action="store_true",
        default=True, help="Colorize diff output"),
    arg("--summary-only", action="store_true", help="Show summary only"),
    arg("--output-file", help="Save comparison to file"),

    # Filtering
    arg("-l", "--selector", help="Label selector"),
    arg("--field-selector", help="Field selector"),
])
class CompareCommand:
    """Compare Kubernetes resources across environments"""

    def __init__(self, kube):
        self.kube = kube
        self.comparisons = []
        self.differences = []

    def execute(self, args):
        """Execute comparison"""
        # Validate arguments
        if not self.validate_args(args):
            return

        # Determine comparison targets
        targets = self.get_comparison_targets(args)

        if len(targets) < 2:
            Logger.error("Need at least 2 targets to compare")
            return

        Logger.info(
            f"Comparing {args.resource_type} across {len(targets)} environments...")

        # Fetch resources from all targets
        resources_by_target = {}
        for target in targets:
            Logger.verbose_log(f"Fetching from {target['label']}...")
            resources = self.fetch_resources(target, args)
            resources_by_target[target['label']] = resources

        # Compare resources
        self.compare_resources(resources_by_target, args)

        # Display results
        self.display_results(args, targets)

        # Save to file if requested
        if args.output_file:
            self.save_to_file(args.output_file, args.output)

    def validate_args(self, args) -> bool:
        """Validate command arguments"""
        # Need either contexts or namespaces, or from/to pairs
        has_contexts = bool(args.contexts)
        has_namespaces = bool(args.namespaces)
        has_from_to = bool(args.from_context or args.from_namespace)

        if not (has_contexts or has_namespaces or has_from_to):
            Logger.error(
                "Specify --contexts, --namespaces, or --from-*/--to-* options")
            return False

        return True

    def get_comparison_targets(self, args) -> List[Dict[str, str]]:
        """Get list of comparison targets"""
        targets = []

        # Multiple contexts
        if args.contexts:
            contexts = args.contexts.split(',')
            for ctx in contexts:
                targets.append({
                    'context': ctx.strip(),
                    'namespace': args.namespace if hasattr(args, 'namespace') else 'default',
                    'label': ctx.strip()
                })

        # Multiple namespaces (same context)
        elif args.namespaces:
            namespaces = args.namespaces.split(',')
            current_context = self.kube.get_current_context()
            for ns in namespaces:
                targets.append({
                    'context': current_context,
                    'namespace': ns.strip(),
                    'label': ns.strip()
                })

        # From/To comparison
        elif args.from_context or args.from_namespace:
            # Source
            targets.append({
                'context': args.from_context or self.kube.get_current_context(),
                'namespace': args.from_namespace or self.kube.namespace,
                'label': f"{args.from_context or 'current'}/{args.from_namespace or self.kube.namespace}"
            })

            # Target
            targets.append({
                'context': args.to_context or self.kube.get_current_context(),
                'namespace': args.to_namespace or self.kube.namespace,
                'label': f"{args.to_context or 'current'}/{args.to_namespace or self.kube.namespace}"
            })

        return targets

    def fetch_resources(self, target: Dict[str, str], args) -> Dict[str, Dict]:
        """Fetch resources from a target"""
        cmd = [
            "get", args.resource_type,
            "-n", target['namespace'],
            "-o", "json"
        ]

        # Add context if different from current
        if target['context'] != self.kube.get_current_context():
            cmd.extend(["--context", target['context']])

        # Add selectors
        if args.selector:
            cmd.extend(["-l", args.selector])

        if args.field_selector:
            cmd.extend(["--field-selector", args.field_selector])

        # Add specific resource if provided
        if args.resource_name:
            cmd.append(args.resource_name)

        try:
            result = self.kube.run(cmd, check=False)
            if result.returncode != 0:
                Logger.warn(f"Failed to fetch from {target['label']}")
                return {}

            data = json.loads(result.stdout)

            # Handle both single resource and list
            if 'items' in data:
                resources = {item['metadata']['name']
                    : item for item in data['items']}
            else:
                resources = {data['metadata']['name']: data}

            return resources

        except Exception as e:
            Logger.error(f"Error fetching from {target['label']}: {e}")
            return {}

    def compare_resources(self, resources_by_target: Dict[str, Dict], args):
        """Compare resources across targets"""
        # Get all unique resource names
        all_names = set()
        for resources in resources_by_target.values():
            all_names.update(resources.keys())

        # Compare each resource
        for name in sorted(all_names):
            comparison = {
                'name': name,
                'exists_in': {},
                'differences': []
            }

            # Check existence in each target
            resource_versions = {}
            for target_label, resources in resources_by_target.items():
                if name in resources:
                    comparison['exists_in'][target_label] = True
                    resource_versions[target_label] = resources[name]
                else:
                    comparison['exists_in'][target_label] = False

            # If resource exists in multiple targets, compare them
            if len(resource_versions) > 1:
                diffs = self.compare_resource_versions(resource_versions, args)
                comparison['differences'] = diffs

                if diffs or args.show_all:
                    self.comparisons.append(comparison)
                    if diffs:
                        self.differences.append(comparison)
            else:
                # Resource only exists in one target
                comparison['differences'] = [
                    'Resource exists in only one environment']
                self.comparisons.append(comparison)
                self.differences.append(comparison)

    def compare_resource_versions(self, versions: Dict[str, Dict], args) -> List[Dict]:
        """Compare different versions of the same resource"""
        differences = []

        # Clean resources for comparison
        cleaned_versions = {}
        for label, resource in versions.items():
            cleaned_versions[label] = self.clean_resource(resource, args)

        # Compare each pair
        labels = list(cleaned_versions.keys())
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                label1, label2 = labels[i], labels[j]
                res1, res2 = cleaned_versions[label1], cleaned_versions[label2]

                diffs = self.find_differences(res1, res2, label1, label2, args)
                differences.extend(diffs)

        return differences

    def clean_resource(self, resource: Dict, args) -> Dict:
        """Clean resource by removing irrelevant fields"""
        cleaned = json.loads(json.dumps(resource))  # Deep copy

        # Remove metadata if requested
        if args.ignore_metadata:
            if 'metadata' in cleaned:
                # Keep only name
                cleaned['metadata'] = {'name': cleaned['metadata'].get('name')}
        else:
            # Always remove runtime metadata
            if 'metadata' in cleaned:
                for field in ['resourceVersion', 'uid', 'selfLink', 'creationTimestamp',
                              'generation', 'managedFields']:
                    cleaned['metadata'].pop(field, None)

        # Remove status if requested
        if args.ignore_status:
            cleaned.pop('status', None)

        # Remove specified fields
        if args.ignore_fields:
            ignore_fields = args.ignore_fields.split(',')
            for field in ignore_fields:
                self.remove_field(cleaned, field.strip())

        return cleaned

    def remove_field(self, obj: Dict, path: str):
        """Remove field by path (e.g., 'spec.replicas')"""
        parts = path.split('.')
        current = obj

        for part in parts[:-1]:
            if part in current:
                current = current[part]
            else:
                return

        current.pop(parts[-1], None)

    def find_differences(self, res1: Dict, res2: Dict,
                         label1: str, label2: str, args) -> List[Dict]:
        """Find differences between two resources"""
        differences = []

        # Compare specific fields if requested
        if args.fields:
            fields = args.fields.split(',')
            for field in fields:
                val1 = self.get_field_value(res1, field.strip())
                val2 = self.get_field_value(res2, field.strip())

                if val1 != val2:
                    differences.append({
                        'field': field.strip(),
                        'env1': label1,
                        'value1': val1,
                        'env2': label2,
                        'value2': val2
                    })
        else:
            # Deep comparison
            diffs = self.deep_compare(res1, res2, label1, label2)
            differences.extend(diffs)

        return differences

    def get_field_value(self, obj: Dict, path: str) -> Any:
        """Get field value by path"""
        parts = path.split('.')
        current = obj

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def deep_compare(self, obj1: Any, obj2: Any,
                     label1: str, label2: str, path: str = "") -> List[Dict]:
        """Deep compare two objects"""
        differences = []

        # Different types
        if type(obj1) != type(obj2):
            differences.append({
                'field': path or 'root',
                'env1': label1,
                'value1': obj1,
                'env2': label2,
                'value2': obj2,
                'type': 'type_mismatch'
            })
            return differences

        # Compare dicts
        if isinstance(obj1, dict):
            all_keys = set(obj1.keys()) | set(obj2.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key

                if key not in obj1:
                    differences.append({
                        'field': new_path,
                        'env1': label1,
                        'value1': None,
                        'env2': label2,
                        'value2': obj2[key],
                        'type': 'missing_in_env1'
                    })
                elif key not in obj2:
                    differences.append({
                        'field': new_path,
                        'env1': label1,
                        'value1': obj1[key],
                        'env2': label2,
                        'value2': None,
                        'type': 'missing_in_env2'
                    })
                else:
                    diffs = self.deep_compare(
                        obj1[key], obj2[key], label1, label2, new_path)
                    differences.extend(diffs)

        # Compare lists
        elif isinstance(obj1, list):
            if len(obj1) != len(obj2):
                differences.append({
                    'field': path,
                    'env1': label1,
                    'value1': f"list length: {len(obj1)}",
                    'env2': label2,
                    'value2': f"list length: {len(obj2)}",
                    'type': 'list_length'
                })
            else:
                for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                    new_path = f"{path}[{i}]"
                    diffs = self.deep_compare(
                        item1, item2, label1, label2, new_path)
                    differences.extend(diffs)

        # Compare primitives
        else:
            if obj1 != obj2:
                differences.append({
                    'field': path,
                    'env1': label1,
                    'value1': obj1,
                    'env2': label2,
                    'value2': obj2,
                    'type': 'value_difference'
                })

        return differences

    def display_results(self, args, targets: List[Dict]):
        """Display comparison results"""
        if args.summary_only:
            self.display_summary(targets)
        elif args.output == "table":
            self.display_table(targets)
        elif args.output == "yaml":
            self.display_yaml()
        elif args.output == "json":
            self.display_json()
        elif args.output == "diff":
            self.display_diff(args, targets)

    def display_summary(self, targets: List[Dict]):
        """Display summary of differences"""
        print(f"\n{Colors.BOLD}COMPARISON SUMMARY{Colors.RESET}")
        print("=" * 60)

        target_labels = [t['label'] for t in targets]
        print(f"Environments: {', '.join(target_labels)}")
        print(f"Total resources compared: {len(self.comparisons)}")
        print(f"Resources with differences: {len(self.differences)}")

        if self.differences:
            print(f"\n{Colors.YELLOW}Resources with differences:{Colors.RESET}")
            for comp in self.differences:
                exists_summary = ", ".join([
                    f"{label}: {'✓' if exists else '✗'}"
                    for label, exists in comp['exists_in'].items()
                ])
                diff_count = len(comp['differences'])
                print(
                    f"  • {comp['name']} ({exists_summary}) - {diff_count} difference(s)")

    def display_table(self, targets: List[Dict]):
        """Display comparison as table"""
        print(f"\n{Colors.BOLD}COMPARISON RESULTS{Colors.RESET}")
        print("=" * 80)

        for comp in self.comparisons:
            if not comp['differences'] and not self.show_all:
                continue

            print(f"\n{Colors.BOLD}{comp['name']}{Colors.RESET}")

            # Existence table
            exists_data = [[label, '✓' if exists else '✗']
                           for label, exists in comp['exists_in'].items()]
            print(format_table(exists_data, ['Environment', 'Exists']))

            # Differences
            if comp['differences']:
                print(f"\n{Colors.YELLOW}Differences:{Colors.RESET}")
                for diff in comp['differences']:
                    if isinstance(diff, str):
                        print(f"  • {diff}")
                    else:
                        field = diff.get('field', 'unknown')
                        val1 = self.format_value(diff.get('value1'))
                        val2 = self.format_value(diff.get('value2'))
                        env1 = diff.get('env1', '')
                        env2 = diff.get('env2', '')

                        print(f"  • {field}:")
                        print(f"    {env1}: {val1}")
                        print(f"    {env2}: {val2}")

    def display_yaml(self):
        """Display comparison as YAML"""
        output = {
            'comparisons': self.comparisons,
            'summary': {
                'total': len(self.comparisons),
                'with_differences': len(self.differences)
            }
        }
        print(yaml.dump(output, default_flow_style=False))

    def display_json(self):
        """Display comparison as JSON"""
        output = {
            'comparisons': self.comparisons,
            'summary': {
                'total': len(self.comparisons),
                'with_differences': len(self.differences)
            }
        }
        print(json.dumps(output, indent=2))

    def display_diff(self, args, targets: List[Dict]):
        """Display unified diff"""
        if len(targets) != 2:
            Logger.error("Diff output requires exactly 2 targets")
            return

        label1, label2 = targets[0]['label'], targets[1]['label']

        for comp in self.comparisons:
            if not comp['differences']:
                continue

            print(
                f"\n{Colors.BOLD}diff {label1}/{comp['name']} {label2}/{comp['name']}{Colors.RESET}")
            print("-" * 60)

            # Get resources
            # This would need actual resource fetching logic
            print("(Diff display implementation)")

    def format_value(self, value: Any) -> str:
        """Format value for display"""
        if value is None:
            return f"{Colors.RED}(missing){Colors.RESET}"
        elif isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        else:
            return str(value)

    def save_to_file(self, filepath: str, format: str):
        """Save comparison results to file"""
        output = {
            'comparisons': self.comparisons,
            'summary': {
                'total': len(self.comparisons),
                'with_differences': len(self.differences)
            }
        }

        path = Path(filepath)

        if format == "json":
            path.write_text(json.dumps(output, indent=2))
        elif format == "yaml":
            path.write_text(yaml.dump(output, default_flow_style=False))
        else:
            path.write_text(str(output))

        Logger.success(f"Comparison saved to {filepath}")


# Usage examples
"""
# Compare deployments across dev, staging, prod
python k8s-mgr.py compare deployment --contexts=dev,staging,prod

# Compare specific deployment
python k8s-mgr.py compare deployment backend --contexts=dev,prod

# Compare across namespaces in same cluster
python k8s-mgr.py compare service --namespaces=default,production,staging

# Compare from one env to another
python k8s-mgr.py compare deployment backend \\
  --from-context=staging --from-namespace=default \\
  --to-context=prod --to-namespace=production

# Compare specific fields only
python k8s-mgr.py compare deployment \\
  --contexts=dev,prod \\
  --fields=spec.replicas,spec.template.spec.containers[0].image

# Ignore metadata and status
python k8s-mgr.py compare deployment \\
  --contexts=dev,prod \\
  --ignore-metadata \\
  --ignore-status

# Output as diff
python k8s-mgr.py compare deployment backend \\
  --from-context=dev --to-context=prod \\
  --output=diff

# Save comparison to file
python k8s-mgr.py compare deployment \\
  --contexts=dev,staging,prod \\
  --output=json \\
  --output-file=comparison.json

# Show all resources, not just different ones
python k8s-mgr.py compare service --contexts=dev,prod --show-all

# Summary only
python k8s-mgr.py compare deployment --contexts=dev,staging,prod --summary-only
"""
