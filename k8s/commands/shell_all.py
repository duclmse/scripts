
"""Multi-shell tmux session for multiple pods"""
import subprocess
from core.decorators import Command, arg
from core.logger import Logger

@Command.register("shell-all", help="Open tmux with shells to multiple pods", args=[
    arg("-l", "--selector", required=True, help="Label selector"),
    arg("--layout", default="tiled", choices=["tiled", "even-horizontal", "even-vertical"], 
        help="Tmux layout"),
    arg("--session", default="k8s-shells", help="Tmux session name"),
])
class ShellAllCommand:
    """Open multiple pod shells in tmux"""
    
    def __init__(self, kube):
        self.kube = kube
    
    def execute(self, args):
        pods = self.kube.get_pods(args.selector)
        
        if not pods:
            Logger.error(f"No pods found with selector '{args.selector}'")
            return
        
        Logger.info(f"Opening shells to {len(pods)} pods in tmux...")
        
        # Create tmux session
        session = args.session
        
        # Kill existing session if exists
        subprocess.run(["tmux", "kill-session", "-t", session], 
                      stderr=subprocess.DEVNULL)
        
        # Create new session with first pod
        subprocess.run([
            "tmux", "new-session", "-d", "-s", session,
            "kubectl", "exec", "-it", "-n", self.kube.namespace, pods[0], "--", "sh"
        ])
        
        # Add panes for remaining pods
        for pod in pods[1:]:
            subprocess.run([
                "tmux", "split-window", "-t", session,
                "kubectl", "exec", "-it", "-n", self.kube.namespace, pod, "--", "sh"
            ])
            subprocess.run(["tmux", "select-layout", "-t", session, args.layout])
        
        # Attach to session
        subprocess.run(["tmux", "attach-session", "-t", session])
