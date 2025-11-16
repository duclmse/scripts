import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("ev", aliases=["event", "events"], help="Watch cluster events", args=[
    arg("-w", "--watch", action="store_true", help="Watch for new events"),
    arg("--for", dest="for_resource", help="Filter by resource"),
    arg("--types", help="Filter by types (Normal,Warning)"),
])
class EventsCommand:
    """Handle events subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        cmd = ["get", "events", "-n", self.kube.namespace]

        if args.watch:
            cmd.append("--watch")

        if args.for_resource:
            cmd.extend(["--for", args.for_resource])

        if args.types:
            cmd.extend(["--types", args.types])

        cmd.append("--sort-by=.lastTimestamp")

        self.kube.run(cmd, capture_output=False)
