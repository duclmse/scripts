import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("logs", aliases=["l"], help="View pod logs", args=[
    arg("pod_name", nargs="?", help="Pod name"),
    arg("-c", "--container", help="Container name"),
    arg("-f", "--follow", action="store_true", help="Follow log output"),
    arg("-t", "--tail", type=int, default=100, help="Number of lines"),
    arg("--since", help="Show logs since duration (e.g., 5m, 1h)"),
    arg("--timestamps", action="store_true", help="Show timestamps"),
    arg("--all-containers", action="store_true", help="All containers"),
    arg("--previous", action="store_true", help="Previous container"),
])
class LogsCommand:
    """Handle logs subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        pod_name = args.pod_name
        if args.app:
            pod_name = self.kube.get_pod(args.app)

        if not pod_name:
            Logger.error("POD_NAME is required")
            sys.exit(1)

        cmd = ["logs", "-n", self.kube.namespace, f"--tail={args.tail}"]

        if args.follow:
            cmd.append("--follow")
        if args.timestamps:
            cmd.append("--timestamps")
        if args.previous:
            cmd.append("--previous")
        if args.all_containers:
            cmd.append("--all-containers")
        if args.since:
            cmd.append(f"--since={args.since}")
        if args.container:
            cmd.extend(["-c", args.container])

        cmd.append(pod_name)

        self.kube.run(cmd, capture_output=False)
