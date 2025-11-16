"""
Port Forward Command - Unified port forwarding with TUI
Replaces: port_forward.py + ports.py
"""

import json
import os
import signal
import subprocess
import time
from typing import Optional
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors
from ..config import KubeConfig

try:
    from blessed import Terminal
    HAS_BLESSED = True
except ImportError:
    HAS_BLESSED = False


@Command.register(
    name="port-forward",
    aliases=["pf", "ports"],
    help="Manage port forwarding",
    args=[
        arg("action", nargs="?", choices=["list", "start", "stop", "stopall", "test", "tui"],
            help="Action to perform (default: tui if blessed installed, else list)"),
        arg("resource", nargs="?", help="Resource (pod/service name or type/name)"),
        arg("ports", nargs="?", help="Port mapping (local:remote or just port)"),

        # Start options
        arg("--address", default="127.0.0.1", help="Bind address (default: 127.0.0.1)"),
        arg("-l", "--selector", help="Label selector to find pod"),

        # Display options
        arg("--show-inactive", action="store_true", help="Show stopped forwards"),
        arg("--json", action="store_true", help="Output as JSON"),

        # Test options
        arg("--protocol", choices=["tcp", "http", "https"], default="tcp", help="Protocol to test"),
    ]
)
class PortForwardCommand:
    """Unified port forward manager with CLI and TUI"""

    def __init__(self, kube):
        self.kube = kube
        self.config = KubeConfig()

    def execute(self, args):
        """Execute port forward command"""
        # Default action
        if not args.action:
            # If blessed available, use TUI, else list
            if HAS_BLESSED:
                args.action = "tui"
            else:
                args.action = "list"

        if args.action == "list":
            self.list_forwards(args)
        elif args.action == "start":
            self.start_forward(args)
        elif args.action == "stop":
            self.stop_forward(args)
        elif args.action == "stopall":
            self.stop_all_forwards(args)
        elif args.action == "test":
            self.test_connection(args)
        elif args.action == "tui":
            self.interactive_tui(args)

    def list_forwards(self, args):
        """List all port forwards"""
        forwards = self.config.get_forwards()

        if not forwards and not args.show_inactive:
            print("No active port forwards")
            return

        # Update status
        for fwd in forwards:
            fwd['status'] = self.check_forward_status(fwd['id'])

        if args.json:
            print(json.dumps(forwards, indent=2))
            return

        # Display table
        print(f"\\n{Colors.BOLD}Port Forwards{Colors.RESET}")
        print("=" * 100)

        data = []
        for fwd in forwards:
            if not args.show_inactive and fwd['status'] != 'running':
                continue

            status_colored = self.colorize_status(fwd['status'])
            ports = fwd.get('ports', 'N/A')
            local_port = ports.split(':')[0] if ':' in ports else ports

            data.append([
                str(fwd['id']),
                fwd.get('resource', 'N/A'),
                local_port,
                ports,
                fwd.get('namespace', 'default'),
                status_colored,
                self.format_uptime(fwd.get('started', 0))
            ])

        if not data:
            print("No port forwards found")
            return

        # Print header
        headers = ['PID', 'RESOURCE', 'LOCAL', 'MAPPING', 'NAMESPACE', 'STATUS', 'UPTIME']
        col_widths = [8, 25, 8, 15, 15, 12, 10]

        header_line = ""
        for i, h in enumerate(headers):
            header_line += h.ljust(col_widths[i]) + "  "
        print(header_line)
        print("─" * 100)

        # Print rows (handle colors)
        for row in data:
            line = ""
            for i, cell in enumerate(row):
                cell_str = str(cell)
                if Colors.RESET in cell_str:
                    import re
                    plain = re.sub(r'\\033\\[[0-9;]+m', '', cell_str)
                    padding = col_widths[i] - len(plain)
                    line += cell_str + (" " * padding) + "  "
                else:
                    line += cell_str.ljust(col_widths[i]) + "  "
            print(line)

        print(f"\\n{Colors.CYAN}Total: {len(data)} active{Colors.RESET}")

        # Show access URLs
        for fwd in forwards:
            if fwd['status'] == 'running':
                ports = fwd.get('ports', '')
                local_port = ports.split(':')[0] if ':' in ports else ports
                print(f"  → http://{fwd.get('address', '127.0.0.1')}:{local_port}")

    def start_forward(self, args):
        """Start a port forward"""
        if not args.resource or not args.ports:
            Logger.error("Resource and ports required")
            Logger.info("Usage: port-forward start <pod-name> <local:remote>")
            Logger.info("   or: port-forward start service/my-svc 8080:80")
            return

        # Parse resource
        resource_type, resource_name = self.parse_resource(args.resource)

        # Get actual pod if service
        if resource_type == "service":
            pod_name = self.get_pod_for_service(resource_name)
            if not pod_name:
                Logger.error(f"No pod found for service {resource_name}")
                return
            resource_name = pod_name
            resource_type = "pod"
        elif resource_type == "pod" and args.selector:
            pods = self.kube.get_pods(args.selector)
            if not pods:
                Logger.error(f"No pod found with selector {args.selector}")
                return
            resource_name = pods[0]

        # Parse ports
        if ':' in args.ports:
            local_port, remote_port = args.ports.split(':', 1)
        else:
            local_port = remote_port = args.ports

        # Check if port already in use
        if self.is_port_in_use(local_port):
            Logger.error(f"Port {local_port} is already in use")
            return

        Logger.info(f"Starting port forward: {resource_name} {local_port}:{remote_port}")

        # Start kubectl port-forward
        cmd = [
            "kubectl", "port-forward",
            f"{resource_type}/{resource_name}",
            f"{local_port}:{remote_port}",
            "-n", self.kube.namespace,
            "--address", args.address
        ]

        # Start in background
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )

        # Wait to check if started
        time.sleep(0.5)

        if proc.poll() is not None:
            Logger.error("Failed to start port forward")
            stderr = proc.stderr.read().decode()
            print(stderr)
            return

        # Save to database
        forward = {
            'id': proc.pid,
            'resource': f"{resource_type}/{resource_name}",
            'ports': f"{local_port}:{remote_port}",
            'address': args.address,
            'namespace': self.kube.namespace,
            'started': int(time.time())
        }

        forwards = self.config.get_forwards()
        forwards.append(forward)
        self.config.save_forwards(forwards)

        Logger.success(f"Port forward started (PID: {proc.pid})")
        Logger.info(f"Access at: http://{args.address}:{local_port}")

    def stop_forward(self, args):
        """Stop a specific port forward"""
        if not args.resource:
            Logger.error("Specify PID or resource name to stop")
            return

        forwards = self.config.get_forwards()

        # Try PID first
        try:
            pid = int(args.resource)
            self.kill_forward(pid)
            forwards = [f for f in forwards if f['id'] != pid]
            self.config.save_forwards(forwards)
            Logger.success(f"Stopped port forward (PID: {pid})")
            return
        except ValueError:
            pass

        # Find by resource name
        resource = args.resource
        found = False

        for fwd in forwards:
            if resource in fwd.get('resource', ''):
                self.kill_forward(fwd['id'])
                forwards = [f for f in forwards if f['id'] != fwd['id']]
                Logger.success(f"Stopped port forward for {fwd['resource']}")
                found = True

        if found:
            self.config.save_forwards(forwards)
        else:
            Logger.error(f"Port forward not found: {resource}")

    def stop_all_forwards(self, args):
        """Stop all port forwards"""
        forwards = self.config.get_forwards()

        if not forwards:
            Logger.info("No port forwards to stop")
            return

        Logger.info(f"Stopping {len(forwards)} port forward(s)...")

        for fwd in forwards:
            self.kill_forward(fwd['id'])

        self.config.save_forwards([])
        Logger.success("All port forwards stopped")

    def test_connection(self, args):
        """Test port forward connection"""
        if not args.resource:
            Logger.error("Specify local port to test")
            return

        try:
            port = int(args.resource)
        except ValueError:
            Logger.error("Invalid port number")
            return

        Logger.info(f"Testing connection to localhost:{port}...")

        if args.protocol in ['http', 'https']:
            self.test_http(port, args.protocol)
        else:
            self.test_tcp(port)

    def test_tcp(self, port: int):
        """Test TCP connection"""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()

            if result == 0:
                Logger.success(f"Port {port} is reachable")
            else:
                Logger.error(f"Port {port} is not reachable")
        except Exception as e:
            Logger.error(f"Connection test failed: {e}")

    def test_http(self, port: int, protocol: str):
        """Test HTTP/HTTPS connection"""
        import urllib.request
        import urllib.error

        url = f"{protocol}://127.0.0.1:{port}"

        try:
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req, timeout=3)
            Logger.success(f"HTTP connection successful (Status: {response.status})")
            print(f"URL: {url}")
        except urllib.error.HTTPError as e:
            Logger.warn(f"HTTP Error: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            Logger.error(f"Connection failed: {e.reason}")
        except Exception as e:
            Logger.error(f"Test failed: {e}")

    def interactive_tui(self, args):
        """Interactive TUI mode"""
        if not HAS_BLESSED:
            Logger.warn("Interactive TUI requires 'blessed' library")
            Logger.info("Install with: pip install blessed")
            Logger.info("Falling back to list mode...")
            self.list_forwards(args)
            return

        tui = PortForwardTUI(self.kube, self.config)
        tui.run()

    # Helper methods
    def parse_resource(self, resource: str) -> list:
        if '/' in resource:
            return resource.split('/', 1)
        return ['pod', resource]

    def get_pod_for_service(self, service_name: str) -> Optional[str]:
        try:
            result = self.kube.run([
                "get", "service", service_name,
                "-n", self.kube.namespace,
                "-o", "jsonpath={.spec.selector}"
            ])
            selector_dict = json.loads(result.stdout)
            selector = ','.join([f"{k}={v}" for k, v in selector_dict.items()])
            pods = self.kube.get_pods(selector)
            return pods[0] if pods else None
        except Exception:
            return None

    def is_port_in_use(self, port: str) -> bool:
        import socket
        try:
            port_num = int(port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port_num))
            sock.close()
            return result == 0
        except Exception:
            return False

    def check_forward_status(self, pid: int) -> str:
        try:
            os.kill(pid, 0)
            return 'running'
        except (OSError, ProcessLookupError):
            return 'stopped'

    def kill_forward(self, pid: int):
        try:
            if os.name == 'nt':
                os.kill(pid, signal.SIGTERM)
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    def colorize_status(self, status: str) -> str:
        if status == 'running':
            return f"{Colors.GREEN}{status}{Colors.RESET}"
        return f"{Colors.RED}{status}{Colors.RESET}"

    def format_uptime(self, started: int) -> str:
        if not started:
            return "N/A"
        uptime = int(time.time()) - started
        if uptime < 60:
            return f"{uptime}s"
        elif uptime < 3600:
            return f"{uptime // 60}m"
        elif uptime < 86400:
            return f"{uptime // 3600}h"
        return f"{uptime // 86400}d"


class PortForwardTUI:
    """Interactive TUI for port forward management"""

    def __init__(self, kube, config):
        self.kube = kube
        self.config = config
        self.term = Terminal()
        self.running = True
        self.selected_index = 0
        self.forwards = []

    def run(self):
        with self.term.fullscreen(), self.term.cbreak(), self.term.hidden_cursor():
            while self.running:
                self.refresh_data()
                self.render()
                key = self.term.inkey(timeout=1)
                if key:
                    self.handle_key(key)

    def refresh_data(self):
        self.forwards = self.config.get_forwards()
        for fwd in self.forwards:
            try:
                os.kill(fwd['id'], 0)
                fwd['status'] = 'running'
            except Exception:
                fwd['status'] = 'stopped'

    def render(self):
        print(self.term.home + self.term.clear)
        title = "Port Forward Manager"
        print(self.term.move_xy(0, 0) + self.term.black_on_white +
              self.term.center(title) + self.term.normal)

        # List forwards
        y = 3
        for i, fwd in enumerate(self.forwards):
            if i == self.selected_index:
                style = self.term.black_on_white
            else:
                style = self.term.normal

            status_color = self.term.green if fwd['status'] == 'running' else self.term.red
            line = f"{fwd['id']:<8} {fwd['resource']:<30} {fwd['ports']:<15} {status_color}{fwd['status']}{self.term.normal}"
            print(self.term.move_xy(2, y + i) + style + line + self.term.normal)

        # Status bar
        status = "↑↓ Navigate | d Delete | t Test | r Refresh | q Quit"
        print(self.term.move_xy(0, self.term.height - 1) + self.term.black_on_white +
              status.ljust(self.term.width) + self.term.normal)

    def handle_key(self, key):
        key_str = str(key).lower()
        if key.code == self.term.KEY_UP or key_str == 'k':
            self.selected_index = max(0, self.selected_index - 1)
        elif key.code == self.term.KEY_DOWN or key_str == 'j':
            self.selected_index = min(len(self.forwards) - 1, self.selected_index + 1)
        elif key_str == 'd' and self.forwards:
            fwd = self.forwards[self.selected_index]
            try:
                os.kill(fwd['id'], signal.SIGTERM)
            except Exception:
                pass
            forwards = [f for f in self.forwards if f['id'] != fwd['id']]
            self.config.save_forwards(forwards)
        elif key_str == 'r':
            self.refresh_data()
        elif key_str == 'q':
            self.running = False
