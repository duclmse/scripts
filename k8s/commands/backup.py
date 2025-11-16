
from pathlib import Path
import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("backup", aliases=["bak"], help="Backup resources", args=[
    arg("output_dir", help="Output directory"),
    arg("-l", "--selector", help="Label selector"),
    arg("-t", "--types", default="all", help="Resource types (comma-separated)"),
    arg("--all-namespaces", action="store_true", help="Backup all namespaces"),
])
class BackupCommand:
    """Handle backup subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not args.output_dir:
            Logger.error("OUTPUT_DIR is required")
            sys.exit(1)

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        Logger.info(f"Backing up to {output_dir}")

        types = args.types.split(",") if args.types != "all" else \
            ["pods", "services", "deployments",
                "configmaps", "secrets", "ingresses"]

        for resource_type in types:
            Logger.info(f"Backing up {resource_type}...")

            cmd = ["get", resource_type, "-n",
                   self.kube.namespace, "-o", "yaml"]

            if args.all_namespaces:
                cmd = ["get", resource_type, "--all-namespaces", "-o", "yaml"]

            if args.selector:
                cmd.extend(["-l", args.selector])

            result = self.kube.run(cmd, check=False)

            if result.returncode == 0:
                output_file = output_dir / f"{resource_type}.yaml"
                output_file.write_text(result.stdout)
            else:
                Logger.warn(f"No {resource_type} found")

        Logger.success(f"Backup completed to {output_dir}")
