
import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("s", aliases=["scale"], help="Scale resources", args=[
    arg("resource_name", help="Resource name"),
    arg("--replicas", type=int, required=True, help="Number of replicas"),
    arg("-t", "--type", default="deployment", help="Resource type"),
])
class ScaleCommand:
    """Handle scale subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not args.resource_name or args.replicas is None:
            Logger.error("RESOURCE_NAME and --replicas are required")
            sys.exit(1)

        Logger.info(
            f"Scaling {args.type}/{args.resource_name} to {args.replicas} replicas")

        self.kube.run([
            "scale", args.type, args.resource_name,
            "-n", self.kube.namespace,
            f"--replicas={args.replicas}"
        ], capture_output=False)

        Logger.success(f"Scaled to {args.replicas} replicas")
