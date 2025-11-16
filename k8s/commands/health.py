
"""Health check dashboard"""
import time
import subprocess
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors

@Command.register("health", help="Real-time health dashboard", args=[
    arg("-i", "--interval", type=int, default=5, help="Refresh interval"),
    arg("-l", "--selector", help="Label selector"),
])
class HealthCommand:
    """Real-time health monitoring"""
    
    def __init__(self, kube):
        self.kube = kube
    
    def execute(self, args):
        try:
            while True:
                self.clear_screen()
                self.show_dashboard(args)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nExiting...")
    
    def clear_screen(self):
        """Clear terminal screen"""
        print("\033[2J\033[H", end="")
    
    def show_dashboard(self, args):
        """Display health dashboard"""
        print(f"{Colors.BOLD}=== KUBERNETES HEALTH DASHBOARD ==={Colors.RESET}")
        print(f"Namespace: {self.kube.namespace}\n")
        
        # Get pods
        cmd = ["get", "pods", "-n", self.kube.namespace, "-o", "json"]
        if args.selector:
            cmd.extend(["-l", args.selector])
        
        result = self.kube.run(cmd)
        
        import json
        data = json.loads(result.stdout)
        
        running = failing = pending = 0
        restarts = []
        
        for pod in data.get('items', []):
            status = pod['status']['phase']
            pod_name = pod['metadata']['name']
            
            if status == 'Running':
                running += 1
            elif status in ['Failed', 'CrashLoopBackOff']:
                failing += 1
            elif status == 'Pending':
                pending += 1
            
            # Check restarts
            for container in pod['status'].get('containerStatuses', []):
                restart_count = container['restartCount']
                if restart_count > 0:
                    restarts.append((pod_name, restart_count))
        
        # Summary
        print(f"{Colors.GREEN}Running:{Colors.RESET} {running}  ", end="")
        print(f"{Colors.RED}Failing:{Colors.RESET} {failing}  ", end="")
        print(f"{Colors.YELLOW}Pending:{Colors.RESET} {pending}\n")
        
        # Restarts
        if restarts:
            print(f"{Colors.BOLD}Pods with Restarts:{Colors.RESET}")
            for pod, count in sorted(restarts, key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {Colors.YELLOW}•{Colors.RESET} {pod}: {count} restarts")
        
        print(f"\n{Colors.CYAN}Press Ctrl+C to exit{Colors.RESET}")
