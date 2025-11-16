
from core.decorators import Command, arg
from core.kubectl import KubeCommand


@Command.register("t", aliases=["top"], help="Show resource usage", args=[
    arg("resource", nargs="?", default="pods", choices=["pods", "nodes"],
        help="Resource type"),
    arg("-l", "--selector", help="Label selector"),
    arg("--sort-by", choices=["cpu", "memory"], help="Sort by metric"),
])
class TopCommand:
    """Handle top subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        resource = args.resource

        cmd = ["top", resource]

        if resource == "pods":
            cmd.extend(["-n", self.kube.namespace])

        if args.selector:
            cmd.extend(["-l", args.selector])

        if args.sort_by:
            cmd.extend(["--sort-by", args.sort_by])

        self.kube.run(cmd, capture_output=False)
