import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("dbg", aliases=["debug"], help="Debug pod with ephemeral container", args=[
    arg("pod_name", nargs="?", help="Pod name"),
    arg("--image", default="busybox", help="Debug image"),
    arg("--target", help="Target container"),
])
class DebugCommand:
    """Handle debug subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        pod_name = args.pod_name
        if args.app:
            pod_name = self.kube.get_pod(args.app)

        if not pod_name:
            Logger.error("POD_NAME is required")
            sys.exit(1)

        Logger.info(f"Starting debug session for {pod_name}")

        cmd = [
            "debug", "-n", self.kube.namespace,
            f"--image={args.image}",
            "-it"
        ]

        if args.target:
            cmd.extend(["--target", args.target])

        cmd.append(pod_name)

        self.kube.run(cmd, capture_output=False)
