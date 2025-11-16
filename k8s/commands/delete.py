import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("d", aliases=["delete", "del"], help="Delete a resource", args=[
    arg("resource_name", nargs="?", help="Resource name"),
    arg("-t", "--type", default="pod", help="Resource type"),
    arg("-f", "--force", action="store_true", help="Force deletion"),
    arg("--grace-period", type=int, default=30, help="Grace period"),
])
class DeleteCommand:
    """Handle delete subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        resource_name = args.resource_name
        if args.app:
            resource_name = self.kube.get_pod(args.app)

        if not resource_name:
            Logger.error("RESOURCE_NAME is required")
            sys.exit(1)

        Logger.warn(
            f"Deleting {args.type}/{resource_name} in namespace {self.kube.namespace}")

        cmd = [
            "delete", args.type, resource_name,
            "-n", self.kube.namespace,
            f"--grace-period={args.grace_period}"
        ]

        if args.force:
            cmd.append("--force")

        self.kube.run(cmd, capture_output=False)
        Logger.success(f"Deleted {args.type}/{resource_name}")
