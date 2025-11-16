
"""Smart restart strategies"""
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger
import time


@Command.register("restart", help="Restart pods with strategies", args=[
    arg("deployment", help="Deployment name"),
    arg("--strategy", default="rolling",
        choices=["rolling", "immediate", "one-by-one"],
        help="Restart strategy"),
    arg("--wait", type=int, default=30,
        help="Wait time between restarts (one-by-one)"),
])
class RestartCommand:
    """Smart restart with different strategies"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        match args.strategy:
            case "rolling":
                self.rolling_restart(args.deployment)
            case "immediate":
                self.immediate_restart(args.deployment)
            case "one-by-one":
                self.one_by_one_restart(args.deployment, args.wait)

    def rolling_restart(self, deployment):
        """Standard rolling restart"""
        Logger.info(f"Rolling restart of {deployment}...")
        self.kube.run([
            "rollout", "restart", f"deployment/{deployment}",
            "-n", self.kube.namespace
        ], capture_output=False)
        Logger.success("Rolling restart initiated")

    def immediate_restart(self, deployment):
        """Immediate restart (scale to 0 then back)"""
        Logger.warn("Immediate restart will cause downtime!")

        # Get current replicas
        result = self.kube.run([
            "get", "deployment", deployment,
            "-n", self.kube.namespace,
            "-o", "jsonpath={.spec.replicas}"
        ])
        replicas = result.stdout.strip()

        Logger.info("Scaling to 0...")
        self.kube.run([
            "scale", f"deployment/{deployment}",
            "-n", self.kube.namespace,
            "--replicas=0"
        ], capture_output=False)

        time.sleep(5)

        Logger.info(f"Scaling back to {replicas}...")
        self.kube.run([
            "scale", f"deployment/{deployment}",
            "-n", self.kube.namespace,
            f"--replicas={replicas}"
        ], capture_output=False)

        Logger.success("Immediate restart completed")

    def one_by_one_restart(self, deployment, wait_time):
        """Restart pods one by one"""
        Logger.info("One-by-one restart...")

        # Get pods
        pods = self.kube.get_pods(f"app={deployment}")

        for i, pod in enumerate(pods, 1):
            Logger.info(f"Restarting pod {i}/{len(pods)}: {pod}")

            self.kube.run([
                "delete", "pod", pod,
                "-n", self.kube.namespace
            ], capture_output=False)

            if i < len(pods):
                Logger.info(f"Waiting {wait_time}s before next restart...")
                time.sleep(wait_time)

        Logger.success("All pods restarted")
