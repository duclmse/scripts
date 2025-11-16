import subprocess
import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("w", aliases=["watch"], help="Watch resource changes", args=[
    arg("resource_type", nargs="?", default="pods", help="Resource type"),
    arg("resource_name", nargs="?", help="Resource name"),
    arg("-l", "--selector", help="Label selector"),
    arg("-i", "--interval", type=int, default=2, help="Refresh interval"),
])
class WatchCommand:
    """Handle watch subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        cmd = ["get", args.resource_type]

        if args.resource_name:
            cmd.append(args.resource_name)

        cmd.extend(["-n", self.kube.namespace])

        if args.selector:
            cmd.extend(["-l", args.selector])

        # Use watch command
        watch_cmd = ["watch", "-n", str(args.interval), "kubectl"] + cmd

        subprocess.run(watch_cmd)
