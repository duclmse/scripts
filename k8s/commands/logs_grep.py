import subprocess
import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("logs-grep", aliases=["lg"], help="Search logs with pattern", args=[
    arg("pod_name", help="Pod name"),
    arg("pattern", help="Search pattern"),
    arg("-t", "--tail", type=int, default=1000, help="Lines to search"),
    arg("-i", "--ignore-case", action="store_true", help="Case insensitive"),
    arg("-A", "--after-context", type=int, help="Lines after match"),
    arg("-B", "--before-context", type=int, help="Lines before match"),
])
class LogsGrepCommand:
    """Handle logs-grep subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        pod_name = args.pod_name
        if args.app:
            pod_name = self.kube.get_pod(args.app)

        if not pod_name or not args.pattern:
            Logger.error("POD_NAME and PATTERN are required")
            sys.exit(1)

        Logger.verbose_log(
            f"Searching for pattern '{args.pattern}' in {pod_name}")

        result = self.kube.run([
            "logs", "-n", self.kube.namespace,
            f"--tail={args.tail}",
            pod_name
        ])

        # Grep through logs
        grep_flags = []
        if args.ignore_case:
            grep_flags.append("-i")
        if args.after_context:
            grep_flags.extend(["-A", str(args.after_context)])
        if args.before_context:
            grep_flags.extend(["-B", str(args.before_context)])

        grep_cmd = ["grep", "--color=always"] + grep_flags + [args.pattern]

        grep_proc = subprocess.run(
            grep_cmd,
            input=result.stdout,
            text=True,
            capture_output=True
        )

        print(grep_proc.stdout)
