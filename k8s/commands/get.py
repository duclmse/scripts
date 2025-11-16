
"""Quick get command with smart resource detection"""
from core.decorators import Command, arg
from core.logger import Logger


@Command.register("get", aliases=["g"], help="Quick get resource with smart detection", args=[
    arg("resource", help="Resource name or pattern"),
    arg("-t", "--type", help="Override resource type"),
    arg("-w", "--watch", action="store_true", help="Watch for changes"),
])
class GetCommand:
    """Smart resource retrieval"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        resource_type = args.type or self.detect_type(args.resource)

        cmd = ["get", resource_type, "-n", self.kube.namespace]

        if not args.type:
            cmd.append(args.resource)

        if args.watch:
            cmd.append("--watch")

        cmd.extend(["-o", "wide"])

        self.kube.run(cmd, capture_output=False)

    def detect_type(self, name: str) -> str:
        """Detect resource type from name pattern"""
        patterns = {
            "pod": ["pod-", "-pod"],
            "deployment": ["deploy-", "-deployment"],
            "service": ["svc-", "-service", "-svc"],
            "configmap": ["cm-", "-configmap", "-cm"],
            "secret": ["secret-"],
        }

        for rtype, patterns_list in patterns.items():
            if any(p in name.lower() for p in patterns_list):
                return rtype

        return "pod"  # Default
