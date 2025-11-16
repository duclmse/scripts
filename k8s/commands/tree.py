import sys
from core.colors import Colors
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("tree", help="Show resource hierarchy", args=[
    arg("deployment", help="Deployment name"),
])
class TreeCommand:
    """Handle tree subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not args.deployment:
            Logger.error("DEPLOYMENT_NAME is required")
            sys.exit(1)

        deployment = args.deployment

        print(f"{Colors.BOLD}{Colors.BLUE}Deployment:{Colors.RESET} {deployment}")

        # Get ReplicaSets
        result = self.kube.run([
            "get", "rs",
            "-n", self.kube.namespace,
            "-l", f"app={deployment}",
            "-o", "jsonpath={.items[*].metadata.name}"
        ])

        replicasets = result.stdout.split()

        for i, rs in enumerate(replicasets):
            # Get replica count
            result = self.kube.run([
                "get", "rs", rs,
                "-n", self.kube.namespace,
                "-o", "jsonpath={.status.replicas}"
            ])
            replicas = result.stdout

            is_last_rs = i == len(replicasets) - 1
            rs_prefix = "└─" if is_last_rs else "├─"

            print(
                f"  {Colors.BOLD}{Colors.GREEN}{rs_prefix} ReplicaSet:{Colors.RESET} {rs} (replicas: {replicas})")

            # Get pods
            hash_part = rs.split('-')[-1]
            result = self.kube.run([
                "get", "pods",
                "-n", self.kube.namespace,
                "-l", f"pod-template-hash={hash_part}",
                "-o", "jsonpath={.items[*].metadata.name}"
            ], check=False)

            pods = result.stdout.split()

            for j, pod in enumerate(pods):
                # Get pod status
                result = self.kube.run([
                    "get", "pod", pod,
                    "-n", self.kube.namespace,
                    "-o", "jsonpath={.status.phase}"
                ])
                status = result.stdout

                is_last_pod = j == len(pods) - 1
                pod_prefix = "└─" if is_last_pod else "├─"
                pod_line_prefix = "   " if is_last_rs else "│  "

                status_color = Colors.GREEN if status == "Running" else Colors.YELLOW
                print(
                    f"  {pod_line_prefix}{pod_prefix} {Colors.BOLD}{status_color}Pod:{Colors.RESET} {pod} ({status})")
