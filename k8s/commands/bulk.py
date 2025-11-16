"""
Bulk Operations Command - Perform actions on multiple resources
"""

import json
import time
from typing import List, Dict, Any
from pathlib import Path
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors


@Command.register("bulk", help="Bulk operations on resources", args=[
    arg("action", choices=[
        "delete", "restart", "scale", "label", "annotate",
        "exec", "logs", "describe", "patch"
    ], help="Bulk action to perform"),
    arg("-l", "--selector", help="Label selector to filter resources"),
    arg("-t", "--type", default="pod", help="Resource type (default: pod)"),
    arg("--dry-run", action="store_true", help="Show what would be done"),
    arg("--confirm", action="store_true", help="Skip confirmation prompt"),
    arg("--parallel", type=int, default=1, help="Number of parallel operations"),
    arg("--delay", type=int, default=0, help="Delay between operations (seconds)"),
    arg("--continue-on-error", action="store_true",
        help="Continue if an operation fails"),

    # Action-specific arguments
    arg("--replicas", type=int, help="Scale: number of replicas"),
    arg("--labels", help="Label: labels to add (key1=value1,key2=value2)"),
    arg("--annotations", help="Annotate: annotations to add"),
    arg("--command", nargs="*", help="Exec: command to execute"),
    arg("--patch", help="Patch: JSON patch to apply"),
    arg("--patch-file", help="Patch: file containing JSON patch"),

    # Filtering
    arg("--field-selector", help="Field selector (e.g., status.phase=Running)"),
    arg("--exclude", help="Exclude resources matching pattern"),
    arg("--include", help="Only include resources matching pattern"),
    arg("--max-resources", type=int, help="Maximum number of resources to process"),

    # Output
    arg("--output-file", help="Save results to file"),
    arg("--summary", action="store_true", help="Show summary only"),
])
class BulkCommand:
    """Perform bulk operations on multiple Kubernetes resources"""

    def __init__(self, kube):
        self.kube = kube
        self.results = {
            'success': [],
            'failed': [],
            'skipped': []
        }

    def execute(self, args):
        """Execute bulk operation"""
        # Validate arguments
        if not self.validate_args(args):
            return

        # Get resources
        resources = self.get_resources(args)

        if not resources:
            Logger.warn(f"No {args.type} resources found matching criteria")
            return

        # Filter resources
        resources = self.filter_resources(resources, args)

        if not resources:
            Logger.warn("No resources remain after filtering")
            return

        # Limit resources if requested
        if args.max_resources:
            original_count = len(resources)
            resources = resources[:args.max_resources]
            if original_count > args.max_resources:
                Logger.info(
                    f"Limited to {args.max_resources} of {original_count} resources")

        # Show what will be done
        self.show_preview(resources, args)

        # Confirm unless --confirm or --dry-run
        if not args.dry_run and not args.confirm:
            if not self.confirm_action(args.action, len(resources)):
                Logger.info("Operation cancelled")
                return

        # Perform bulk operation
        if args.dry_run:
            Logger.info("Dry run - no changes made")
        else:
            self.perform_bulk_operation(resources, args)

        # Show results
        self.show_results(args)

    def validate_args(self, args) -> bool:
        """Validate command arguments"""
        # Action-specific validation
        if args.action == "scale" and args.replicas is None:
            Logger.error("--replicas required for scale action")
            return False

        if args.action == "label" and not args.labels:
            Logger.error("--labels required for label action")
            return False

        if args.action == "annotate" and not args.annotations:
            Logger.error("--annotations required for annotate action")
            return False

        if args.action == "exec" and not args.command:
            Logger.error("--command required for exec action")
            return False

        if args.action == "patch" and not args.patch and not args.patch_file:
            Logger.error("--patch or --patch-file required for patch action")
            return False

        return True

    def get_resources(self, args) -> List[Dict[str, Any]]:
        """Get resources matching criteria"""
        cmd = ["get", args.type, "-n", self.kube.namespace, "-o", "json"]

        if args.selector:
            cmd.extend(["-l", args.selector])

        if args.field_selector:
            cmd.extend(["--field-selector", args.field_selector])

        try:
            result = self.kube.run(cmd)
            data = json.loads(result.stdout)
            return data.get('items', [])
        except Exception as e:
            Logger.error(f"Failed to get resources: {e}")
            return []

    def filter_resources(self, resources: List[Dict], args) -> List[Dict]:
        """Apply additional filtering"""
        filtered = resources

        # Exclude pattern
        if args.exclude:
            filtered = [r for r in filtered
                        if args.exclude not in r['metadata']['name']]

        # Include pattern
        if args.include:
            filtered = [r for r in filtered
                        if args.include in r['metadata']['name']]

        return filtered

    def show_preview(self, resources: List[Dict], args):
        """Show preview of what will be done"""
        Logger.info(
            f"Will perform {Colors.BOLD}{args.action}{Colors.RESET} on {len(resources)} {args.type}(s):")

        # Show first 10 resources
        for i, resource in enumerate(resources[:10], 1):
            name = resource['metadata']['name']

            # Show additional info based on action
            info = ""
            if args.action == "scale":
                current = resource.get('spec', {}).get('replicas', 'N/A')
                info = f" ({current} -> {args.replicas} replicas)"
            elif args.action == "delete":
                status = resource.get('status', {}).get('phase', 'Unknown')
                info = f" (status: {status})"

            print(f"  {i}. {name}{info}")

        if len(resources) > 10:
            print(f"  ... and {len(resources) - 10} more")

        print()

    def confirm_action(self, action: str, count: int) -> bool:
        """Ask for confirmation"""
        print(f"{Colors.YELLOW}⚠ About to {action} {count} resource(s){Colors.RESET}")
        response = input("Continue? [y/N]: ").strip().lower()
        return response in ['y', 'yes']

    def perform_bulk_operation(self, resources: List[Dict], args):
        """Perform the bulk operation"""
        total = len(resources)
        Logger.info(f"Processing {total} resource(s)...")

        for i, resource in enumerate(resources, 1):
            name = resource['metadata']['name']

            Logger.info(f"[{i}/{total}] Processing {name}...")

            try:
                # Perform action
                if args.action == "delete":
                    self.bulk_delete(name, args)
                elif args.action == "restart":
                    self.bulk_restart(name, args)
                elif args.action == "scale":
                    self.bulk_scale(name, args)
                elif args.action == "label":
                    self.bulk_label(name, args)
                elif args.action == "annotate":
                    self.bulk_annotate(name, args)
                elif args.action == "exec":
                    self.bulk_exec(name, args)
                elif args.action == "logs":
                    self.bulk_logs(name, args)
                elif args.action == "describe":
                    self.bulk_describe(name, args)
                elif args.action == "patch":
                    self.bulk_patch(name, args)

                self.results['success'].append(name)
                Logger.success(f"Completed: {name}")

            except Exception as e:
                Logger.error(f"Failed: {name} - {e}")
                self.results['failed'].append({'name': name, 'error': str(e)})

                if not args.continue_on_error:
                    Logger.error(
                        "Stopping due to error (use --continue-on-error to continue)")
                    break

            # Delay between operations
            if args.delay > 0 and i < total:
                Logger.verbose_log(
                    f"Waiting {args.delay}s before next operation...")
                time.sleep(args.delay)

    def bulk_delete(self, name: str, args):
        """Delete a resource"""
        self.kube.run([
            "delete", args.type, name,
            "-n", self.kube.namespace
        ])

    def bulk_restart(self, name: str, args):
        """Restart a resource"""
        if args.type == "pod":
            # Delete pod to restart
            self.kube.run([
                "delete", "pod", name,
                "-n", self.kube.namespace
            ])
        elif args.type == "deployment":
            # Rollout restart
            self.kube.run([
                "rollout", "restart", f"deployment/{name}",
                "-n", self.kube.namespace
            ])
        else:
            raise ValueError(f"Restart not supported for {args.type}")

    def bulk_scale(self, name: str, args):
        """Scale a resource"""
        self.kube.run([
            "scale", args.type, name,
            "-n", self.kube.namespace,
            f"--replicas={args.replicas}"
        ])

    def bulk_label(self, name: str, args):
        """Add labels to resource"""
        labels = args.labels.split(',')
        for label in labels:
            self.kube.run([
                "label", args.type, name,
                "-n", self.kube.namespace,
                label,
                "--overwrite"
            ])

    def bulk_annotate(self, name: str, args):
        """Add annotations to resource"""
        annotations = args.annotations.split(',')
        for annotation in annotations:
            self.kube.run([
                "annotate", args.type, name,
                "-n", self.kube.namespace,
                annotation,
                "--overwrite"
            ])

    def bulk_exec(self, name: str, args):
        """Execute command in pod"""
        if args.type != "pod":
            raise ValueError("Exec only works with pods")

        result = self.kube.run([
            "exec", name,
            "-n", self.kube.namespace,
            "--"
        ] + args.command, capture_output=True, check=False)

        if result.returncode != 0:
            raise Exception(f"Command failed: {result.stderr}")

        # Store output
        self.results['success'].append({
            'name': name,
            'output': result.stdout
        })

    def bulk_logs(self, name: str, args):
        """Get logs from pods"""
        if args.type != "pod":
            raise ValueError("Logs only work with pods")

        result = self.kube.run([
            "logs", name,
            "-n", self.kube.namespace,
            "--tail=50"
        ], capture_output=True, check=False)

        if result.returncode == 0:
            print(f"\n{Colors.BOLD}=== Logs from {name} ==={Colors.RESET}")
            print(result.stdout)

    def bulk_describe(self, name: str, args):
        """Describe resources"""
        result = self.kube.run([
            "describe", args.type, name,
            "-n", self.kube.namespace
        ], capture_output=True)

        print(f"\n{Colors.BOLD}=== {name} ==={Colors.RESET}")
        print(result.stdout)

    def bulk_patch(self, name: str, args):
        """Apply JSON patch to resource"""
        # Get patch content
        if args.patch_file:
            patch_content = Path(args.patch_file).read_text()
        else:
            patch_content = args.patch

        self.kube.run([
            "patch", args.type, name,
            "-n", self.kube.namespace,
            "--type=merge",
            "-p", patch_content
        ])

    def show_results(self, args):
        """Show operation results"""
        print()
        print("=" * 60)
        print(f"{Colors.BOLD}BULK OPERATION RESULTS{Colors.RESET}")
        print("=" * 60)

        success_count = len(self.results['success'])
        failed_count = len(self.results['failed'])
        skipped_count = len(self.results['skipped'])
        total = success_count + failed_count + skipped_count

        # Summary
        print(f"\n{Colors.GREEN}✓ Success:{Colors.RESET} {success_count}/{total}")
        if failed_count > 0:
            print(f"{Colors.RED}✗ Failed:{Colors.RESET}  {failed_count}/{total}")
        if skipped_count > 0:
            print(f"{Colors.YELLOW}○ Skipped:{Colors.RESET} {skipped_count}/{total}")

        # Show failures
        if failed_count > 0 and not args.summary:
            print(f"\n{Colors.RED}Failed operations:{Colors.RESET}")
            for failure in self.results['failed']:
                if isinstance(failure, dict):
                    print(f"  • {failure['name']}: {failure['error']}")
                else:
                    print(f"  • {failure}")

        # Save results to file if requested
        if args.output_file:
            self.save_results(args.output_file)
            Logger.success(f"Results saved to {args.output_file}")

        print()

    def save_results(self, filepath: str):
        """Save results to file"""
        output = {
            'action': 'bulk_operation',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'success': len(self.results['success']),
                'failed': len(self.results['failed']),
                'skipped': len(self.results['skipped'])
            },
            'details': self.results
        }

        Path(filepath).write_text(json.dumps(output, indent=2))


# Usage examples
"""
# Delete all pods with label app=backend
python k8s-mgr.py bulk delete -l app=backend -t pod

# Scale all deployments matching pattern
python k8s-mgr.py bulk scale -l tier=frontend --replicas=3 -t deployment

# Restart all pods one by one with 30s delay
python k8s-mgr.py bulk restart -l app=backend --delay=30 -t pod

# Add label to all services
python k8s-mgr.py bulk label -l env=prod --labels="monitored=true,team=platform" -t service

# Execute command in all pods
python k8s-mgr.py bulk exec -l app=backend --command ps aux -t pod

# Get logs from all pods (first 50 lines each)
python k8s-mgr.py bulk logs -l app=backend -t pod

# Dry run - see what would be deleted
python k8s-mgr.py bulk delete -l app=test --dry-run

# Continue on errors and save results
python k8s-mgr.py bulk delete -l app=old --continue-on-error --output-file=results.json

# Patch all deployments
python k8s-mgr.py bulk patch -l app=backend -t deployment --patch='{"spec":{"replicas":3}}'

# Filter with exclude/include
python k8s-mgr.py bulk delete -l app=test --exclude="production" --include="staging"

# Limit number of resources
python k8s-mgr.py bulk restart -l app=backend --max-resources=5
"""
