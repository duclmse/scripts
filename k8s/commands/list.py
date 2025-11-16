from core.decorators import Command, arg
from core.kubectl import KubeCommand


@Command.register("ls", aliases=["list"], help="Enhanced resource listing", args=[
    arg("resource_type", nargs="?", default="pods", help="Resource type"),
    arg("-l", "--selector", help="Label selector"),
    arg("-w", "--watch", action="store_true", help="Watch for changes"),
    arg("--sort-by", help="Sort by field"),
    arg("--all-namespaces", action="store_true",
        help="List across all namespaces"),
])
class ListCommand:
    """Handle list subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        cmd = ["get", args.resource_type]

        if not args.all_namespaces:
            cmd.extend(["-n", self.kube.namespace])
        else:
            cmd.append("--all-namespaces")

        if args.selector:
            cmd.extend(["-l", args.selector])

        if args.sort_by:
            cmd.extend(["--sort-by", args.sort_by])

        if args.watch:
            cmd.append("--watch")

        self.kube.run(cmd, capture_output=False)
