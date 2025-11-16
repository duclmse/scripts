"""
Alerts Command - Watch and send notifications
"""

import json
import time
import subprocess
from datetime import datetime
from core.decorators import Command, arg
from core.logger import Logger


@Command.register(
    name="alerts",
    aliases=["al", "alert"],
    help="Watch resources and send alerts",
    args=[
        arg("resource_type", nargs="?", default="pods", help="Resource type to watch"),
        arg("--condition", help="Alert condition (e.g., 'status!=Running')"),
        arg("--email", help="Email address for alerts"),
        arg("--slack-webhook", help="Slack webhook URL"),
        arg("--webhook", help="Generic webhook URL"),
        arg("-i", "--interval", type=int, default=30, help="Check interval (seconds)"),
        arg("-l", "--selector", help="Label selector"),
        arg("--threshold", type=int, default=1, help="Alert after N occurrences"),
    ]
)
class AlertsCommand:
    """Watch resources and send notifications on changes"""

    def __init__(self, kube):
        self.kube = kube
        self.alert_history = {}
        self.alert_count = {}

    def execute(self, args):
        """Execute alerts command"""
        if not any([args.email, args.slack_webhook, args.webhook]):
            Logger.error("Specify at least one alert method: --email, --slack-webhook, or --webhook")
            return

        Logger.info(f"Starting alert monitoring for {args.resource_type}")
        Logger.info(f"Check interval: {args.interval}s")
        Logger.info(f"Alert threshold: {args.threshold}")

        try:
            while True:
                self.check_resources(args)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            Logger.info("\\nStopping alert monitoring")

    def check_resources(self, args):
        """Check resources and send alerts"""
        cmd = ["get", args.resource_type, "-n", self.kube.namespace, "-o", "json"]

        if args.selector:
            cmd.extend(["-l", args.selector])

        try:
            result = self.kube.run(cmd)
            data = json.loads(result.stdout)

            for item in data.get('items', []):
                name = item['metadata']['name']

                # Check condition
                if self.check_condition(item, args.condition):
                    self.handle_alert(name, item, args)

        except Exception as e:
            Logger.error(f"Check failed: {e}")

    def check_condition(self, resource: dict, condition: str) -> bool:
        """Check if resource matches alert condition"""
        if not condition:
            # Default: alert on non-running pods
            if resource.get('kind') == 'Pod':
                status = resource.get('status', {}).get('phase', '')
                return status not in ['Running', 'Succeeded']
            return False

        # Parse condition (simple implementation)
        # Format: "field!=value" or "field=value"
        if '!=' in condition:
            field, value = condition.split('!=')
            return self.get_field(resource, field.strip()) != value.strip()
        elif '=' in condition:
            field, value = condition.split('=')
            return self.get_field(resource, field.strip()) == value.strip()

        return False

    def get_field(self, resource: dict, field: str) -> str:
        """Get field value from resource"""
        # Simple path traversal (e.g., "status.phase")
        parts = field.split('.')
        current = resource

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, '')
            else:
                return ''

        return str(current)

    def handle_alert(self, name: str, resource: dict, args):
        """Handle alert for resource"""
        # Count occurrences
        self.alert_count[name] = self.alert_count.get(name, 0) + 1

        # Check threshold
        if self.alert_count[name] < args.threshold:
            return

        # Check if already alerted recently (within last 5 minutes)
        last_alert = self.alert_history.get(name)
        if last_alert and (time.time() - last_alert) < 300:
            return

        # Send alert
        message = self.format_alert_message(name, resource)

        if args.email:
            self.send_email_alert(args.email, message)

        if args.slack_webhook:
            self.send_slack_alert(args.slack_webhook, message)

        if args.webhook:
            self.send_webhook_alert(args.webhook, message)

        # Record alert
        self.alert_history[name] = time.time()
        Logger.warn(f"Alert sent for {name}")

    def format_alert_message(self, name: str, resource: dict) -> str:
        """Format alert message"""
        kind = resource.get('kind', 'Resource')
        namespace = resource['metadata'].get('namespace', 'default')

        if kind == 'Pod':
            status = resource.get('status', {}).get('phase', 'Unknown')
            message = f"{kind} '{name}' in namespace '{namespace}' is {status}"

            # Add container status
            container_statuses = resource.get('status', {}).get('containerStatuses', [])
            for cs in container_statuses:
                if cs.get('state', {}).get('waiting'):
                    reason = cs['state']['waiting'].get('reason', '')
                    message += f"\\nContainer waiting: {reason}"
        else:
            message = f"{kind} '{name}' in namespace '{namespace}' triggered alert"

        return message

    def send_email_alert(self, email: str, message: str):
        """Send email alert"""
        # Simple implementation using mail command
        try:
            subprocess.run(
                ["mail", "-s", "Kubernetes Alert", email],
                input=message.encode(),
                check=False
            )
        except Exception as e:
            Logger.error(f"Failed to send email: {e}")

    def send_slack_alert(self, webhook: str, message: str):
        """Send Slack webhook alert"""
        import urllib.request
        import urllib.error

        try:
            payload = json.dumps({"text": message})
            req = urllib.request.Request(
                webhook,
                data=payload.encode(),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req)
        except Exception as e:
            Logger.error(f"Failed to send Slack alert: {e}")

    def send_webhook_alert(self, webhook: str, message: str):
        """Send generic webhook alert"""
        import urllib.request
        import urllib.error

        try:
            payload = json.dumps({
                "timestamp": datetime.now().isoformat(),
                "message": message,
                "source": "k8s-manager"
            })
            req = urllib.request.Request(
                webhook,
                data=payload.encode(),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req)
        except Exception as e:
            Logger.error(f"Failed to send webhook alert: {e}")
