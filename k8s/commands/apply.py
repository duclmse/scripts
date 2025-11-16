from pathlib import Path
import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("apply", help="Apply configuration", args=[
    arg("-f", "--filename", required=True, help="Configuration file"),
    arg("--dry-run", action="store_true", help="Dry run mode"),
    arg("--validate", action="store_true", help="Validate only"),
])
class ApplyCommand:
    """Handle apply subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not args.filename:
            Logger.error("FILE (-f) is required")
            sys.exit(1)

        filepath = Path(args.filename)
        if not filepath.exists():
            Logger.error(f"File not found: {args.filename}")
            sys.exit(1)

        cmd = ["apply", "-n", self.kube.namespace, "-f", args.filename]

        if args.dry_run:
            cmd.append("--dry-run=client")
            Logger.info("Dry run mode - no changes will be applied")

        if args.validate:
            cmd.append("--validate=true")

        self.kube.run(cmd, capture_output=False)

        if not args.dry_run:
            Logger.success(f"Applied configuration from {args.filename}")
