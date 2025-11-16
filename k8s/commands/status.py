import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("status", aliases=["stt"], help="Check resource status", args=[
    arg("resource_name", nargs="?", help="Resource name"),
    arg("-t", "--type", default="pod", help="Resource type"),
    arg("-l", "--selector", help="Label selector"),
    arg("-w", "--watch", action="store_true", help="Watch for changes"),
])
class StatusCommand:
    """Handle status subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        cmd = ["get", args.type, "-n", self.kube.namespace]

        if args.resource_name:
            cmd.append(args.resource_name)

        if args.selector:
            cmd.extend(["-l", args.selector])

        if args.watch:
            cmd.append("--watch")

        cmd.extend(["-o", args.output])

        self.kube.run(cmd, capture_output=False)
