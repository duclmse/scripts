import sys
from core.colors import Colors
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("la", aliases=["logs-all"], help="Tail logs from multiple pods", args=[
    arg("-l", "--selector", required=True, help="Label selector"),
    arg("-t", "--tail", type=int, default=10, help="Lines per pod"),
    arg("--since", help="Show logs since duration"),
])
class LogsAllCommand:
    """Handle logs-all subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not args.selector:
            Logger.error("Label selector (-l) is required")
            sys.exit(1)

        pods = self.kube.get_pods(args.selector)

        if not pods:
            Logger.error(f"No pods found with selector '{args.selector}'")
            sys.exit(1)

        Logger.info(f"Tailing logs from {len(pods)} pod(s)...")

        for pod in pods:
            print(f"\n{Colors.BOLD}{Colors.BLUE}==> {pod} <=={Colors.RESET}")
            cmd = [
                "logs", "-n", self.kube.namespace,
                f"--tail={args.tail}",
                pod
            ]
            if args.since:
                cmd.append(f"--since={args.since}")

            try:
                result = self.kube.run(cmd, check=False)
                print(result.stdout)
            except Exception as e:
                Logger.warn(f"Failed to get logs from {pod}: {e}")
