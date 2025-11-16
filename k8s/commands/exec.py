import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("e", aliases=["exec"], help="Execute command in pod", args=[
    arg("pod_name", nargs="?", help="Pod name"),
    arg("command", nargs="*", help="Command to execute"),
    arg("-c", "--container", help="Container name"),
    arg("-i", "--interactive", action="store_true", default=True,
        help="Interactive mode"),
    arg("-t", "--tty", action="store_true", default=True, help="Allocate TTY"),
    arg("--shell", default="auto", help="Shell to use"),
])
class ExecCommand:
    """Handle exec subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        cmd = self.get_cmd(args)

        Logger.verbose_log(f"Executing: {' '.join(cmd)}")
        self.kube.run(cmd, capture_output=False)

    def get_cmd(self, args):
        pod_name = args.pod_name
        if args.app:
            pod_name = self.kube.get_pod(args.app)

        if not pod_name:
            Logger.error("POD_NAME is required")
            sys.exit(1)
        cmd = ["exec", "-n", self.kube.namespace]

        if args.interactive:
            cmd.append("-i")
        if args.tty:
            cmd.append("-t")
        if args.container:
            cmd.extend(["-c", args.container])

        cmd.append(pod_name)
        cmd.append("--")
        return cmd

    def detect_shell(self, cmd, args, pod_name):
        # Auto-detect shell if no command provided
        if args.command:
            cmd.extend(args.command)
            return
        shell = args.shell if args.shell != "auto" else None
        if not shell:
            for sh in ["bash", "sh", "ash"]:
                test_result = self.kube.run(
                    ["exec", "-n", self.kube.namespace,
                        pod_name, "--", "which", sh],
                    check=False
                )
                if test_result.returncode == 0:
                    shell = sh
                    break
            if not shell:
                shell = "sh"
        cmd.append(shell)
