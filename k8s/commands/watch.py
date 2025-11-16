"""
Watch Command - Simple resource watching
Replaces: Original watch.py (kubectl watch wrapper)
"""

import subprocess
from core.decorators import Command, arg
from core.logger import Logger


@Command.register("watch", aliases=["w"], help="Watch resource changes", args=[
    arg("resource_type", nargs="?", default="pods", help="Resource type"),
    arg("resource_name", nargs="?", help="Specific resource name"),
    arg("-l", "--selector", help="Label selector"),
    arg("-i", "--interval", type=int, default=2, help="Refresh interval (seconds)"),
])
class WatchCommand:
    """Simple resource watching (kubectl watch wrapper)"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        """Execute watch command"""
        cmd = ["get", args.resource_type]

        if args.resource_name:
            cmd.append(args.resource_name)

        cmd.extend(["-n", self.kube.namespace])

        if args.selector:
            cmd.extend(["-l", args.selector])

        # Use watch command or kubectl native watch
        Logger.info(f"Watching {args.resource_type} (Ctrl+C to stop)")

        try:
            # Try using system 'watch' command
            watch_cmd = ["watch", "-n", str(args.interval), "kubectl"] + cmd
            subprocess.run(watch_cmd)
        except FileNotFoundError:
            # Fallback to kubectl watch
            cmd.append("--watch")
            self.kube.run(cmd, capture_output=False)
