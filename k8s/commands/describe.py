import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("desc", aliases=["describe"], help="Describe resources", args=[
    arg("resource_name", nargs="?", help="Resource name"),
    arg("-t", "--type", default="pod", help="Resource type"),
])
class DescribeCommand:
    """Handle describe subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        resource_name = args.resource_name
        if args.app:
            resource_name = self.kube.get_pod(args.app)

        if not resource_name:
            Logger.error("RESOURCE_NAME is required")
            sys.exit(1)

        self.kube.run([
            "describe", args.type, resource_name,
            "-n", self.kube.namespace
        ], capture_output=False)
