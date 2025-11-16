
"""Kubectl command wrapper"""
import subprocess
import sys
from typing import List, Optional
from .logger import Logger

class KubeCommand:
    """Execute kubectl commands"""

    def __init__(self, namespace: str = "default", context: Optional[str] = None, verbose: bool = False):
        self.namespace = namespace
        self.context = context
        self.verbose = verbose
        Logger.verbose = verbose

    def run(self, cmd: List[str], capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
        """Run kubectl command"""
        full_cmd = ["kubectl"] + cmd

        if self.context:
            full_cmd.extend(["--context", self.context])

        Logger.verbose_log(f"Running: {' '.join(full_cmd)}")

        try:
            if capture_output:
                result = subprocess.run(
                    full_cmd, capture_output=True, text=True, check=check)
            else:
                result = subprocess.run(full_cmd, check=check)
            return result
        except subprocess.CalledProcessError as e:
            Logger.error(f"Command failed: {e}")
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            sys.exit(1)

    def get_pod(self, app_label: str) -> str:
        """Get pod name by app label"""
        Logger.verbose_log(f"Getting pod with label app={app_label}")
        result = self.run([
            "get", "pod", "-n", self.namespace,
            "-l", f"app={app_label}",
            "-o", "jsonpath={.items[0].metadata.name}"
        ])

        pod = result.stdout.strip()
        if not pod:
            Logger.error(
                f"No pod found with label 'app={app_label}' in namespace '{self.namespace}'")
            sys.exit(1)
        return pod

    def get_pods(self, selector: str) -> List[str]:
        """Get multiple pods by selector"""
        result = self.run([
            "get", "pods", "-n", self.namespace,
            "-l", selector,
            "-o", "jsonpath={.items[*].metadata.name}"
        ])
        return result.stdout.split()

    @staticmethod
    def get_current_context() -> str:
        """Get current kubectl context"""
        try:
            result = subprocess.run(
                ["kubectl", "config", "current-context"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
