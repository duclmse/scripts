import os
import signal
import subprocess
import sys
import time
from core.colors import Colors
from core.config import KubeConfig
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("pf", aliases=["port-forward"], help="Manage port forwarding", args=[
    arg("action", choices=["start", "list", "stop"], help="Action to perform"),
    arg("pod_name", nargs="?", help="Pod name"),
    arg("ports", nargs="?", help="LOCAL_PORT:REMOTE_PORT"),
    arg("target", nargs="?", default="all", help="PID or 'all' for stop"),
])
class PortForwardCommand:
    """Handle port-forward subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube
        self.config = KubeConfig()

    def execute(self, args):
        action = args.action

        if action == "start":
            self.start(args)
        elif action == "list":
            self.list_forwards()
        elif action == "stop":
            self.stop(args.target)
        else:
            Logger.error(f"Unknown action: {action}")
            sys.exit(1)

    def start(self, args):
        pod_name = args.pod_name
        ports = args.ports

        if not pod_name or not ports:
            Logger.error("POD_NAME and PORTS are required for start")
            sys.exit(1)

        Logger.info(f"Starting port forward: {pod_name} {ports}")

        # Start port forward in background
        proc = subprocess.Popen(
            ["kubectl", "port-forward", "-n", self.kube.namespace, pod_name, ports],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Save to database
        forwards = self.config.get_forwards()
        forwards.append({
            "id": proc.pid,
            "pod": pod_name,
            "ports": ports,
            "namespace": self.kube.namespace,
            "started": int(time.time())
        })
        self.config.save_forwards(forwards)

        Logger.success(f"Port forward started (PID: {proc.pid})")

    def list_forwards(self):
        forwards = self.config.get_forwards()

        print(f"{Colors.BOLD}PID\tPOD\tPORTS\tNAMESPACE\tSTATUS{Colors.RESET}")

        for fwd in forwards:
            pid = fwd["id"]
            status = self.check_process(pid)
            status_color = Colors.GREEN if status == "running" else Colors.RED

            print(
                f"{pid}\t{fwd['pod']}\t{fwd['ports']}\t{fwd['namespace']}\t{status_color}{status}{Colors.RESET}")

    def stop(self, target):
        forwards = self.config.get_forwards()

        if target == "all":
            for fwd in forwards:
                self.kill_process(fwd["id"])
            self.config.save_forwards([])
        else:
            pid = int(target)
            self.kill_process(pid)
            forwards = [f for f in forwards if f["id"] != pid]
            self.config.save_forwards(forwards)

    @staticmethod
    def check_process(pid: int) -> str:
        try:
            os.kill(pid, 0)
            return "running"
        except Exception as e:
            return f"stopped: {e}"

    @staticmethod
    def kill_process(pid: int):
        try:
            os.kill(pid, signal.SIGTERM)
            Logger.success(f"Stopped PID {pid}")
        except Exception as e:
            Logger.warn(f"PID {pid} not found: {e}")
