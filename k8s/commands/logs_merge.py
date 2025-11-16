
"""Merge and deduplicate logs from multiple pods"""
import re
from datetime import datetime
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors


@Command.register("logs-merge", help="Merge logs from multiple pods", args=[
    arg("-l", "--selector", required=True, help="Label selector"),
    arg("-t", "--tail", type=int, default=100, help="Lines per pod"),
    arg("--dedupe", action="store_true", help="Remove duplicate lines"),
    arg("--sort", action="store_true", help="Sort by timestamp"),
])
class LogsMergeCommand:
    """Intelligent log merging"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        pods = self.kube.get_pods(args.selector)

        if not pods:
            Logger.error(f"No pods found with selector '{args.selector}'")
            return

        colors = [Colors.RED, Colors.GREEN, Colors.YELLOW,
                  Colors.BLUE, Colors.MAGENTA, Colors.CYAN]

        all_logs = []
        for i, pod in enumerate(pods):
            color = colors[i % len(colors)]
            result = self.kube.run([
                "logs", "-n", self.kube.namespace, f"--tail={args.tail}", pod
            ], check=False)

            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    timestamp = self.extract_timestamp(line)
                    all_logs.append({
                        'pod': pod,
                        'line': line,
                        'timestamp': timestamp,
                        'color': color
                    })

        # Sort by timestamp if requested
        if args.sort and any(log['timestamp'] for log in all_logs):
            all_logs.sort(key=lambda x: x['timestamp'] or datetime.min)

        # Deduplicate if requested
        if args.dedupe:
            seen = set()
            deduped = []
            for log in all_logs:
                if log['line'] not in seen:
                    seen.add(log['line'])
                    deduped.append(log)
            all_logs = deduped

        # Print merged logs
        for log in all_logs:
            pod_label = f"[{log['pod']}]"
            print(f"{log['color']}{pod_label:30}{Colors.RESET} {log['line']}")

    def extract_timestamp(self, line: str):
        """Extract timestamp from log line"""
        # Common timestamp patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
            r'\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}',
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    return datetime.fromisoformat(match.group().replace(' ', 'T'))
                except Exception:
                    pass
        return None
