import sys
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("ro", aliases=["rollout"], help="Manage rollouts", args=[
    arg("action", choices=["status", "history", "undo", "pause", "resume", "restart"],
        help="Rollout action"),
    arg("deployment", help="Deployment name"),
])
class RolloutCommand:
    """Handle rollout subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not args.deployment:
            Logger.error("DEPLOYMENT_NAME is required")
            sys.exit(1)

        self.kube.run([
            "rollout", args.action,
            f"deployment/{args.deployment}",
            "-n", self.kube.namespace
        ], capture_output=False)
