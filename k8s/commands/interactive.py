"""
Interactive Command - Full-screen terminal UI for Kubernetes management
Requires: pip install blessed
"""

import json
import time
import threading
from datetime import datetime
from core.decorators import Command, arg
from core.logger import Logger

try:
    from blessed import Terminal
    HAS_BLESSED = True
except ImportError:
    HAS_BLESSED = False


@Command.register("interactive", aliases=["i", "tui"], help="Interactive TUI mode", args=[
    arg("--refresh", type=int, default=2,
        help="Refresh interval in seconds (default: 2)"),
    arg("--theme", choices=["dark", "light"],
        default="dark", help="Color theme"),
])
class InteractiveCommand:
    """Full-screen interactive terminal UI"""

    def __init__(self, kube):
        self.kube = kube
        self.term = None
        self.running = True
        self.refresh_interval = 2
        self.current_view = "pods"
        self.selected_index = 0
        self.scroll_offset = 0
        self.filter_text = ""
        self.show_help = False
        self.resources = []
        self.resource_details = None
        self.last_update = None
        self.views = ["pods", "deployments", "services", "nodes", "events"]
        self.view_index = 0

    def execute(self, args):
        """Execute interactive mode"""
        if not HAS_BLESSED:
            Logger.error("Interactive mode requires 'blessed' library")
            print("\nInstall with: pip install blessed")
            return

        self.refresh_interval = args.refresh
        self.term = Terminal()

        try:
            with self.term.fullscreen(), self.term.cbreak(), self.term.hidden_cursor():
                # Start background refresh thread
                refresh_thread = threading.Thread(
                    target=self.refresh_loop, daemon=True)
                refresh_thread.start()

                # Initial load
                self.refresh_data()

                # Main event loop
                self.main_loop()

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            print(self.term.normal)

    def main_loop(self):
        """Main event loop"""
        while self.running:
            self.render()

            # Handle input
            key = self.term.inkey(timeout=0.1)

            if key:
                self.handle_key(key)

    def handle_key(self, key):
        """Handle keyboard input"""
        key_str = str(key).lower()

        # Navigation
        if key.code == self.term.KEY_UP or key_str == 'k':
            self.move_selection(-1)
        elif key.code == self.term.KEY_DOWN or key_str == 'j':
            self.move_selection(1)
        elif key.code == self.term.KEY_PGUP:
            self.move_selection(-10)
        elif key.code == self.term.KEY_PGDOWN:
            self.move_selection(10)
        elif key.code == self.term.KEY_HOME or key_str == 'g':
            self.selected_index = 0
            self.scroll_offset = 0
        elif key.code == self.term.KEY_END or key_str == 'G':
            self.selected_index = max(0, len(self.resources) - 1)

        # View switching
        elif key.code == self.term.KEY_TAB or key_str == '\t':
            self.next_view()
        elif key_str == '1':
            self.switch_view("pods")
        elif key_str == '2':
            self.switch_view("deployments")
        elif key_str == '3':
            self.switch_view("services")
        elif key_str == '4':
            self.switch_view("nodes")
        elif key_str == '5':
            self.switch_view("events")

        # Actions
        elif key.code == self.term.KEY_ENTER or key_str == '\n':
            self.show_details()
        elif key_str == 'd':
            self.delete_resource()
        elif key_str == 'l':
            self.view_logs()
        elif key_str == 'e':
            self.exec_shell()
        elif key_str == 's':
            self.scale_resource()
        elif key_str == 'r':
            self.restart_resource()
        elif key_str == '/':
            self.start_filter()
        elif key.code == self.term.KEY_ESCAPE:
            self.clear_filter()
            self.resource_details = None

        # Help and quit
        elif key_str == '?':
            self.show_help = not self.show_help
        elif key_str == 'q':
            self.running = False
        elif key_str == 'R':  # Capital R for manual refresh
            self.refresh_data()

    def move_selection(self, delta: int):
        """Move selection up or down"""
        if not self.resources:
            return

        self.selected_index = max(
            0, min(len(self.resources) - 1, self.selected_index + delta))

        # Auto-scroll
        visible_lines = self.term.height - 10
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + visible_lines:
            self.scroll_offset = self.selected_index - visible_lines + 1

    def next_view(self):
        """Switch to next view"""
        self.view_index = (self.view_index + 1) % len(self.views)
        self.current_view = self.views[self.view_index]
        self.selected_index = 0
        self.scroll_offset = 0
        self.refresh_data()

    def switch_view(self, view: str):
        """Switch to specific view"""
        if view in self.views:
            self.current_view = view
            self.view_index = self.views.index(view)
            self.selected_index = 0
            self.scroll_offset = 0
            self.refresh_data()

    def refresh_loop(self):
        """Background refresh loop"""
        while self.running:
            time.sleep(self.refresh_interval)
            if not self.show_help and not self.resource_details:
                self.refresh_data()

    def refresh_data(self):
        """Refresh resource data"""
        try:
            if self.current_view == "pods":
                self.resources = self.get_pods()
            elif self.current_view == "deployments":
                self.resources = self.get_deployments()
            elif self.current_view == "services":
                self.resources = self.get_services()
            elif self.current_view == "nodes":
                self.resources = self.get_nodes()
            elif self.current_view == "events":
                self.resources = self.get_events()

            # Apply filter
            if self.filter_text:
                self.resources = [
                    r for r in self.resources if self.filter_text.lower() in r['name'].lower()]

            self.last_update = datetime.now()

            # Adjust selection if out of bounds
            if self.selected_index >= len(self.resources):
                self.selected_index = max(0, len(self.resources) - 1)

        except Exception as e:
            pass  # Silently fail during refresh

    def get_pods(self) -> list[dict]:
        """Get pod list"""
        try:
            result = self.kube.run([
                "get", "pods", "-n", self.kube.namespace, "-o", "json"
            ])
            data = json.loads(result.stdout)

            pods = []
            for item in data.get('items', []):
                status = item.get('status', {})
                phase = status.get('phase', 'Unknown')

                # Count restarts
                restarts = sum(
                    cs.get('restartCount', 0)
                    for cs in status.get('containerStatuses', [])
                )

                pods.append({
                    'name': item['metadata']['name'],
                    'status': phase,
                    'restarts': restarts,
                    'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                    'raw': item
                })

            return pods
        except:
            return []

    def get_deployments(self) -> list[dict]:
        """Get deployment list"""
        try:
            result = self.kube.run([
                "get", "deployments", "-n", self.kube.namespace, "-o", "json"
            ])
            data = json.loads(result.stdout)

            deployments = []
            for item in data.get('items', []):
                spec = item.get('spec', {})
                status = item.get('status', {})

                deployments.append({
                    'name': item['metadata']['name'],
                    'replicas': f"{status.get('readyReplicas', 0)}/{spec.get('replicas', 0)}",
                    'available': status.get('availableReplicas', 0),
                    'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                    'raw': item
                })

            return deployments
        except:
            return []

    def get_services(self) -> list[dict]:
        """Get service list"""
        try:
            result = self.kube.run([
                "get", "services", "-n", self.kube.namespace, "-o", "json"
            ])
            data = json.loads(result.stdout)

            services = []
            for item in data.get('items', []):
                spec = item.get('spec', {})

                services.append({
                    'name': item['metadata']['name'],
                    'type': spec.get('type', 'ClusterIP'),
                    'cluster_ip': spec.get('clusterIP', ''),
                    'ports': ','.join([str(p.get('port', '')) for p in spec.get('ports', [])]),
                    'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                    'raw': item
                })

            return services
        except:
            return []

    def get_nodes(self) -> list[dict]:
        """Get node list"""
        try:
            result = self.kube.run(["get", "nodes", "-o", "json"])
            data = json.loads(result.stdout)

            nodes = []
            for item in data.get('items', []):
                status = item.get('status', {})

                # Get conditions
                ready = "Unknown"
                for condition in status.get('conditions', []):
                    if condition.get('type') == 'Ready':
                        ready = condition.get('status', 'Unknown')

                nodes.append({
                    'name': item['metadata']['name'],
                    'status': ready,
                    'roles': ','.join(item['metadata'].get('labels', {}).get('node-role.kubernetes.io', 'worker').split(',')),
                    'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                    'raw': item
                })

            return nodes
        except:
            return []

    def get_events(self) -> list[dict]:
        """Get recent events"""
        try:
            result = self.kube.run([
                "get", "events", "-n", self.kube.namespace,
                "--sort-by=.lastTimestamp", "-o", "json"
            ])
            data = json.loads(result.stdout)

            events = []
            for item in data.get('items', [])[-50:]:  # Last 50 events
                events.append({
                    'name': f"{item.get('involvedObject', {}).get('name', 'unknown')}",
                    'type': item.get('type', 'Normal'),
                    'reason': item.get('reason', ''),
                    'message': item.get('message', '')[:50],
                    'age': self.get_age(item.get('lastTimestamp', '')),
                    'raw': item
                })

            return list(reversed(events))  # Most recent first
        except:
            return []

    def get_age(self, timestamp: str) -> str:
        """Calculate age from timestamp"""
        try:
            if not timestamp:
                return "unknown"

            from datetime import datetime, timezone
            created = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            delta = now - created

            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60

            if days > 0:
                return f"{days}d"
            elif hours > 0:
                return f"{hours}h"
            else:
                return f"{minutes}m"
        except:
            return "unknown"

    def render(self):
        """Render the UI"""
        print(self.term.home + self.term.clear)

        if self.show_help:
            self.render_help()
        elif self.resource_details:
            self.render_details()
        else:
            self.render_main()

    def render_main(self):
        """Render main view"""
        # Header
        self.render_header()

        # Tabs
        self.render_tabs()

        # Resource list
        self.render_list()

        # Status bar
        self.render_status_bar()

    def render_header(self):
        """Render header"""
        title = f"Kubernetes Interactive Manager - {self.kube.namespace}"
        print(self.term.move_xy(0, 0) + self.term.black_on_white +
              self.term.center(title) + self.term.normal)

    def render_tabs(self):
        """Render view tabs"""
        y = 2
        x = 2

        for i, view in enumerate(self.views):
            if view == self.current_view:
                style = self.term.black_on_green + self.term.bold
            else:
                style = self.term.normal

            display = f" {i+1}:{view.upper()} "
            print(self.term.move_xy(x, y) + style + display + self.term.normal)
            x += len(display) + 2

        # Refresh indicator
        if self.last_update:
            update_str = f"Updated: {self.last_update.strftime('%H:%M:%S')}"
            print(self.term.move_xy(self.term.width -
                  len(update_str) - 2, y) + update_str)

    def render_list(self):
        """Render resource list"""
        start_y = 4
        visible_lines = self.term.height - start_y - 3

        # Headers
        if self.current_view == "pods":
            headers = ["NAME", "STATUS", "RESTARTS", "AGE"]
            col_widths = [40, 15, 10, 10]
        elif self.current_view == "deployments":
            headers = ["NAME", "READY", "AVAILABLE", "AGE"]
            col_widths = [40, 15, 12, 10]
        elif self.current_view == "services":
            headers = ["NAME", "TYPE", "CLUSTER-IP", "PORTS", "AGE"]
            col_widths = [30, 15, 15, 15, 10]
        elif self.current_view == "nodes":
            headers = ["NAME", "STATUS", "ROLES", "AGE"]
            col_widths = [40, 15, 20, 10]
        elif self.current_view == "events":
            headers = ["OBJECT", "TYPE", "REASON", "MESSAGE", "AGE"]
            col_widths = [20, 10, 15, 40, 10]

        # Print headers
        x = 2
        for i, header in enumerate(headers):
            print(self.term.move_xy(x, start_y) + self.term.bold +
                  header.ljust(col_widths[i]) + self.term.normal)
            x += col_widths[i] + 1

        # Print separator
        print(self.term.move_xy(2, start_y + 1) + "─" * (self.term.width - 4))

        # Print resources
        for i in range(visible_lines):
            idx = self.scroll_offset + i

            if idx >= len(self.resources):
                break

            resource = self.resources[idx]
            y = start_y + 2 + i

            # Highlight selected
            if idx == self.selected_index:
                style = self.term.black_on_white
            else:
                style = self.term.normal

            # Format row
            if self.current_view == "pods":
                row = [
                    resource['name'][:col_widths[0]],
                    self.colorize_status(resource['status']),
                    str(resource['restarts']),
                    resource['age']
                ]
            elif self.current_view == "deployments":
                row = [
                    resource['name'][:col_widths[0]],
                    resource['replicas'],
                    str(resource['available']),
                    resource['age']
                ]
            elif self.current_view == "services":
                row = [
                    resource['name'][:col_widths[0]],
                    resource['type'],
                    resource['cluster_ip'],
                    resource['ports'][:col_widths[3]],
                    resource['age']
                ]
            elif self.current_view == "nodes":
                row = [
                    resource['name'][:col_widths[0]],
                    self.colorize_status(resource['status']),
                    resource['roles'][:col_widths[2]],
                    resource['age']
                ]
            elif self.current_view == "events":
                event_color = self.term.red if resource['type'] == 'Warning' else self.term.normal
                row = [
                    resource['name'][:col_widths[0]],
                    event_color + resource['type'] + self.term.normal,
                    resource['reason'][:col_widths[2]],
                    resource['message'][:col_widths[3]],
                    resource['age']
                ]

            # Print row
            x = 2
            for j, cell in enumerate(row):
                print(self.term.move_xy(x, y) + style +
                      str(cell).ljust(col_widths[j]) + self.term.normal)
                x += col_widths[j] + 1

        # Scroll indicator
        if len(self.resources) > visible_lines:
            scroll_info = f"[{self.scroll_offset + 1}-{min(self.scroll_offset + visible_lines, len(self.resources))}/{len(self.resources)}]"
            print(self.term.move_xy(self.term.width -
                  len(scroll_info) - 2, self.term.height - 2) + scroll_info)

    def colorize_status(self, status: str) -> str:
        """Colorize status string"""
        if status in ['Running', 'Ready', 'True']:
            return self.term.green + status + self.term.normal
        elif status in ['Pending', 'Unknown']:
            return self.term.yellow + status + self.term.normal
        else:
            return self.term.red + status + self.term.normal

    def render_status_bar(self):
        """Render status bar at bottom"""
        y = self.term.height - 1

        if self.filter_text:
            status = f"Filter: {self.filter_text} | "
        else:
            status = ""

        status += "? Help | TAB Next | ↑↓ Move | ENTER Details | d Delete | l Logs | q Quit"

        print(self.term.move_xy(0, y) + self.term.black_on_white +
              status.ljust(self.term.width) + self.term.normal)

    def render_help(self):
        """Render help screen"""
        y = 2
        x = 4

        help_text = [
            ("NAVIGATION", ""),
            ("  ↑/k", "Move up"),
            ("  ↓/j", "Move down"),
            ("  PgUp/PgDn", "Page up/down"),
            ("  Home/g", "Go to top"),
            ("  End/G", "Go to bottom"),
            ("", ""),
            ("VIEWS", ""),
            ("  TAB", "Next view"),
            ("  1-5", "Switch to view"),
            ("", ""),
            ("ACTIONS", ""),
            ("  ENTER", "Show details"),
            ("  d", "Delete resource"),
            ("  l", "View logs (pods)"),
            ("  e", "Exec shell (pods)"),
            ("  s", "Scale (deployments)"),
            ("  r", "Restart resource"),
            ("  /", "Start filter"),
            ("  ESC", "Clear filter/close"),
            ("", ""),
            ("OTHER", ""),
            ("  ?", "Toggle help"),
            ("  R", "Refresh now"),
            ("  q", "Quit"),
        ]

        print(self.term.move_xy(x, y) + self.term.bold +
              "KEYBOARD SHORTCUTS" + self.term.normal)
        y += 2

        for key, desc in help_text:
            if not desc:
                print(self.term.move_xy(x, y) +
                      self.term.bold + key + self.term.normal)
            else:
                print(self.term.move_xy(x, y) + self.term.green +
                      key.ljust(20) + self.term.normal + desc)
            y += 1

        print(self.term.move_xy(x, self.term.height - 2) + "Press ? to close help")

    def render_details(self):
        """Render resource details"""
        if not self.resource_details:
            return

        y = 2

        print(self.term.move_xy(2, y) + self.term.bold +
              "RESOURCE DETAILS" + self.term.normal)
        y += 2

        # Display YAML
        lines = self.resource_details.split('\n')
        max_lines = self.term.height - 6

        for i, line in enumerate(lines[:max_lines]):
            print(self.term.move_xy(2, y + i) + line[:self.term.width - 4])

        if len(lines) > max_lines:
            print(self.term.move_xy(2, y + max_lines) + "... (truncated)")

        print(self.term.move_xy(2, self.term.height - 2) + "Press ESC to close")

    def show_details(self):
        """Show resource details"""
        if not self.resources or self.selected_index >= len(self.resources):
            return

        resource = self.resources[self.selected_index]

        try:
            import yaml
            self.resource_details = yaml.dump(
                resource['raw'], default_flow_style=False)
        except:
            self.resource_details = json.dumps(resource['raw'], indent=2)

    def delete_resource(self):
        """Delete selected resource"""
        # This would require confirmation dialog
        # For now, just show message
        pass

    def view_logs(self):
        """View logs for selected pod"""
        if self.current_view != "pods" or not self.resources:
            return

        # Exit TUI and show logs
        self.running = False
        resource = self.resources[self.selected_index]

        print(self.term.clear)
        subprocess.run([
            "kubectl", "logs", resource['name'],
            "-n", self.kube.namespace,
            "--tail=100", "--follow"
        ])

    def exec_shell(self):
        """Exec into selected pod"""
        if self.current_view != "pods" or not self.resources:
            return

        # Exit TUI and exec
        self.running = False
        resource = self.resources[self.selected_index]

        print(self.term.clear)
        subprocess.run([
            "kubectl", "exec", "-it", resource['name'],
            "-n", self.kube.namespace,
            "--", "sh"
        ])

    def scale_resource(self):
        """Scale selected deployment"""
        # Would need input dialog
        pass

    def restart_resource(self):
        """Restart selected resource"""
        pass

    def start_filter(self):
        """Start filtering"""
        # Would need input dialog
        pass

    def clear_filter(self):
        """Clear filter"""
        self.filter_text = ""
        self.refresh_data()


# Usage examples
"""
# Start interactive mode
python k8s-mgr.py interactive

# With custom refresh interval
python k8s-mgr.py interactive --refresh=5

# Short alias
python k8s-mgr.py i

# TUI alias
python k8s-mgr.py tui
"""
