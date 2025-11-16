
"""Network debugging tools"""
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors


@Command.register("netdebug", aliases=["ndbg"], help="Network debugging tools", args=[
    arg("action", choices=["ping", "dns", "endpoints",
        "policies"], help="Debug action"),
    arg("target", nargs="?", help="Target pod or service"),
    arg("--from", dest="from_pod", help="Source pod for testing"),
])
class NetDebugCommand:
    """Network connectivity testing"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        match args.action:
            case "ping":
                self.test_ping(args)
            case "dns":
                self.test_dns(args.target)
            case "endpoints":
                self.show_endpoints(args.target)
            case "policies":
                self.show_network_policies()

    def test_ping(self, args):
        """Test connectivity between pods"""
        if not args.from_pod or not args.target:
            Logger.error("Both --from and target required")
            return

        Logger.info(
            f"Testing connectivity from {args.from_pod} to {args.target}...")

        # Use curl or wget to test
        result = self.kube.run([
            "exec", args.from_pod,
            "-n", self.kube.namespace,
            "--", "sh", "-c",
            f"curl -s -o /dev/null -w '%{{http_code}}' {args.target} || echo 'failed'"
        ], check=False)

        if result.returncode == 0:
            code = result.stdout.strip()
            if code.startswith('2') or code.startswith('3'):
                Logger.success(f"Connection successful (HTTP {code})")
            else:
                Logger.warn(f"Connection returned HTTP {code}")
        else:
            Logger.error("Connection failed")

    def test_dns(self, service):
        """Test DNS resolution"""
        if not service:
            Logger.error("Service name required")
            return

        Logger.info(f"Testing DNS resolution for {service}...")

        # Create test pod
        result = self.kube.run([
            "run", "netdebug-test",
            "--image=busybox",
            "-n", self.kube.namespace,
            "--rm", "-it", "--restart=Never",
            "--", "nslookup", service
        ], capture_output=False, check=False)

        if result.returncode == 0:
            Logger.success("DNS resolution successful")
        else:
            Logger.error("DNS resolution failed")

    def show_endpoints(self, service):
        """Show service endpoints"""
        if not service:
            Logger.error("Service name required")
            return

        Logger.info(f"Endpoints for {service}:")

        self.kube.run([
            "get", "endpoints", service,
            "-n", self.kube.namespace
        ], capture_output=False)

    def show_network_policies(self):
        """Show network policies"""
        Logger.info("Network policies in namespace:")

        self.kube.run([
            "get", "networkpolicies",
            "-n", self.kube.namespace
        ], capture_output=False)
