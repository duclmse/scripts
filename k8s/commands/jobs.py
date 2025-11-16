"""
Jobs Command - Manage Kubernetes Jobs and CronJobs
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors
from utils.formatters import format_table, format_age


@Command.register("jobs", aliases=["job"], help="Manage Jobs and CronJobs", args=[
    arg("action", nargs="?", choices=[
        "list", "create", "run", "delete", "logs", "status",
        "suspend", "resume", "history", "cleanup"
    ], help="Action to perform"),
    arg("name", nargs="?", help="Job or CronJob name"),

    # List options
    arg("--type", choices=["job", "cronjob", "all"], default="all",
        help="Resource type to list"),
    arg("--status", choices=["active", "succeeded", "failed", "all"],
        default="all", help="Filter by status"),
    arg("-l", "--selector", help="Label selector"),
    arg("--show-controlled", action="store_true",
        help="Show jobs created by CronJobs"),

    # Create options
    arg("--image", help="Container image"),
    arg("--command", nargs="*", help="Command to run"),
    arg("--schedule", help="Cron schedule (for CronJob)"),
    arg("--completions", type=int, default=1, help="Number of completions"),
    arg("--parallelism", type=int, default=1, help="Parallelism"),
    arg("--backoff-limit", type=int, default=6, help="Backoff limit"),
    arg("--restart-policy", choices=["Never", "OnFailure"], default="Never",
        help="Restart policy"),
    arg("--ttl-seconds", type=int, help="TTL after finished"),

    # CronJob specific
    arg("--suspend", action="store_true", help="Create suspended CronJob"),
    arg("--concurrency-policy", choices=["Allow", "Forbid", "Replace"],
        default="Allow", help="Concurrency policy"),
    arg("--successful-history", type=int, default=3,
        help="Successful jobs to keep"),
    arg("--failed-history", type=int, default=1, help="Failed jobs to keep"),
    arg("--starting-deadline", type=int, help="Starting deadline seconds"),

    # Run options
    arg("--wait", action="store_true", help="Wait for job completion"),
    arg("--timeout", type=int, default=300, help="Wait timeout (seconds)"),
    arg("--from-cronjob", help="Create job from CronJob"),

    # Cleanup options
    arg("--older-than", help="Delete jobs older than (e.g., 7d, 24h)"),
    arg("--keep-last", type=int, help="Keep last N jobs"),
    arg("--dry-run", action="store_true", help="Show what would be deleted"),

    # Output
    arg("-w", "--watch", action="store_true", help="Watch job status"),
    arg("--follow", action="store_true", help="Follow logs"),
])
class JobsCommand:
    """Manage Kubernetes Jobs and CronJobs"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        """Execute jobs command"""
        action = args.action or "list"

        if action == "list":
            self.list_jobs(args)
        elif action == "create":
            self.create_job(args)
        elif action == "run":
            self.run_job(args)
        elif action == "delete":
            self.delete_job(args)
        elif action == "logs":
            self.show_logs(args)
        elif action == "status":
            self.show_status(args)
        elif action == "suspend":
            self.suspend_cronjob(args)
        elif action == "resume":
            self.resume_cronjob(args)
        elif action == "history":
            self.show_history(args)
        elif action == "cleanup":
            self.cleanup_jobs(args)

    def list_jobs(self, args):
        """List Jobs and CronJobs"""
        print(
            f"\n{Colors.BOLD}Jobs and CronJobs in {self.kube.namespace}{Colors.RESET}")
        print("=" * 80)

        # Get CronJobs
        if args.type in ["cronjob", "all"]:
            cronjobs = self.get_cronjobs(args)
            if cronjobs:
                print(f"\n{Colors.CYAN}CronJobs:{Colors.RESET}")
                self.display_cronjobs(cronjobs)

        # Get Jobs
        if args.type in ["job", "all"]:
            jobs = self.get_jobs(args)
            if jobs:
                print(f"\n{Colors.GREEN}Jobs:{Colors.RESET}")
                self.display_jobs(jobs)

        # Watch mode
        if args.watch:
            self.watch_jobs(args)

    def get_cronjobs(self, args) -> List[Dict]:
        """Get CronJob list"""
        cmd = ["get", "cronjobs", "-n", self.kube.namespace, "-o", "json"]

        if args.selector:
            cmd.extend(["-l", args.selector])

        try:
            result = self.kube.run(cmd)
            data = json.loads(result.stdout)

            cronjobs = []
            for item in data.get('items', []):
                spec = item.get('spec', {})
                status = item.get('status', {})

                cronjobs.append({
                    'name': item['metadata']['name'],
                    'schedule': spec.get('schedule', ''),
                    'suspend': spec.get('suspend', False),
                    'active': len(status.get('active', [])),
                    'last_schedule': status.get('lastScheduleTime', ''),
                    'last_successful': status.get('lastSuccessfulTime', ''),
                    'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                    'raw': item
                })

            return cronjobs
        except Exception as e:
            Logger.error(f"Failed to get CronJobs: {e}")
            return []

    def get_jobs(self, args) -> List[Dict]:
        """Get Job list"""
        cmd = ["get", "jobs", "-n", self.kube.namespace, "-o", "json"]

        if args.selector:
            cmd.extend(["-l", args.selector])

        try:
            result = self.kube.run(cmd)
            data = json.loads(result.stdout)

            jobs = []
            for item in data.get('items', []):
                # Skip jobs created by CronJobs unless requested
                if not args.show_controlled:
                    owner_refs = item['metadata'].get('ownerReferences', [])
                    if any(ref.get('kind') == 'CronJob' for ref in owner_refs):
                        continue

                spec = item.get('spec', {})
                status = item.get('status', {})

                # Determine status
                job_status = self.get_job_status(status)

                # Filter by status
                if args.status != "all":
                    if args.status == "active" and job_status != "Running":
                        continue
                    elif args.status == "succeeded" and job_status != "Succeeded":
                        continue
                    elif args.status == "failed" and job_status != "Failed":
                        continue

                jobs.append({
                    'name': item['metadata']['name'],
                    'completions': f"{status.get('succeeded', 0)}/{spec.get('completions', 1)}",
                    'duration': self.get_duration(status),
                    'status': job_status,
                    'age': self.get_age(item['metadata'].get('creationTimestamp', '')),
                    'raw': item
                })

            return jobs
        except Exception as e:
            Logger.error(f"Failed to get Jobs: {e}")
            return []

    def display_cronjobs(self, cronjobs: List[Dict]):
        """Display CronJobs table"""
        data = []
        for cj in cronjobs:
            suspend_str = "True" if cj['suspend'] else "False"
            last_schedule = self.format_timestamp(cj['last_schedule'])

            data.append([
                cj['name'],
                cj['schedule'],
                suspend_str,
                str(cj['active']),
                last_schedule,
                cj['age']
            ])

        print(format_table(data, ['NAME', 'SCHEDULE',
              'SUSPEND', 'ACTIVE', 'LAST SCHEDULE', 'AGE']))

    def display_jobs(self, jobs: List[Dict]):
        """Display Jobs table"""
        data = []
        for job in jobs:
            status_colored = self.colorize_job_status(job['status'])

            data.append([
                job['name'],
                job['completions'],
                job['duration'],
                status_colored,
                job['age']
            ])

        # Print manually to preserve colors
        headers = ['NAME', 'COMPLETIONS', 'DURATION', 'STATUS', 'AGE']
        col_widths = [40, 15, 15, 15, 10]

        # Headers
        header_line = ""
        for i, header in enumerate(headers):
            header_line += header.ljust(col_widths[i]) + "  "
        print(header_line)
        print("─" * 95)

        # Rows
        for row in data:
            line = ""
            for i, cell in enumerate(row):
                # Remove color codes for padding calculation
                cell_str = str(cell)
                plain_cell = cell_str
                if Colors.RESET in cell_str:
                    # Extract plain text
                    import re
                    plain_cell = re.sub(r'\033\[[0-9;]+m', '', cell_str)

                padding = col_widths[i] - len(plain_cell)
                line += cell_str + (" " * padding) + "  "
            print(line)

    def get_job_status(self, status: Dict) -> str:
        """Determine job status"""
        if status.get('active', 0) > 0:
            return "Running"
        elif status.get('succeeded', 0) > 0:
            return "Succeeded"
        elif status.get('failed', 0) > 0:
            return "Failed"
        else:
            return "Pending"

    def colorize_job_status(self, status: str) -> str:
        """Colorize job status"""
        if status == "Succeeded":
            return f"{Colors.GREEN}{status}{Colors.RESET}"
        elif status == "Failed":
            return f"{Colors.RED}{status}{Colors.RESET}"
        elif status == "Running":
            return f"{Colors.CYAN}{status}{Colors.RESET}"
        else:
            return f"{Colors.YELLOW}{status}{Colors.RESET}"

    def get_duration(self, status: Dict) -> str:
        """Get job duration"""
        start = status.get('startTime')
        completion = status.get('completionTime')

        if not start:
            return "N/A"

        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))

            if completion:
                end_dt = datetime.fromisoformat(
                    completion.replace('Z', '+00:00'))
            else:
                end_dt = datetime.now(start_dt.tzinfo)

            delta = end_dt - start_dt
            return self.format_duration(delta)
        except:
            return "N/A"

    def format_duration(self, delta: timedelta) -> str:
        """Format duration"""
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m{total_seconds % 60}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"

    def get_age(self, timestamp: str) -> str:
        """Get age from timestamp"""
        if not timestamp:
            return "N/A"

        try:
            created = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(created.tzinfo)
            return format_age(now - created)
        except:
            return "N/A"

    def format_timestamp(self, timestamp: str) -> str:
        """Format timestamp"""
        if not timestamp:
            return "Never"

        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo)
            delta = now - dt

            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds // 3600 > 0:
                return f"{delta.seconds // 3600}h ago"
            else:
                return f"{delta.seconds // 60}m ago"
        except:
            return "Unknown"

    def create_job(self, args):
        """Create a new Job or CronJob"""
        if not args.name or not args.image:
            Logger.error("Name and image are required")
            return

        if args.schedule:
            self.create_cronjob(args)
        else:
            self.create_simple_job(args)

    def create_simple_job(self, args):
        """Create a simple Job"""
        Logger.info(f"Creating Job {args.name}...")

        job_spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": args.name,
                "namespace": self.kube.namespace
            },
            "spec": {
                "completions": args.completions,
                "parallelism": args.parallelism,
                "backoffLimit": args.backoff_limit,
                "template": {
                    "spec": {
                        "restartPolicy": args.restart_policy,
                        "containers": [{
                            "name": args.name,
                            "image": args.image,
                        }]
                    }
                }
            }
        }

        # Add command if specified
        if args.command:
            job_spec["spec"]["template"]["spec"]["containers"][0]["command"] = args.command

        # Add TTL if specified
        if args.ttl_seconds:
            job_spec["spec"]["ttlSecondsAfterFinished"] = args.ttl_seconds

        # Apply
        self.apply_manifest(job_spec)
        Logger.success(f"Job {args.name} created")

        # Wait if requested
        if args.wait:
            self.wait_for_job(args.name, args.timeout)

    def create_cronjob(self, args):
        """Create a CronJob"""
        Logger.info(f"Creating CronJob {args.name}...")

        cronjob_spec = {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {
                "name": args.name,
                "namespace": self.kube.namespace
            },
            "spec": {
                "schedule": args.schedule,
                "suspend": args.suspend,
                "concurrencyPolicy": args.concurrency_policy,
                "successfulJobsHistoryLimit": args.successful_history,
                "failedJobsHistoryLimit": args.failed_history,
                "jobTemplate": {
                    "spec": {
                        "completions": args.completions,
                        "parallelism": args.parallelism,
                        "backoffLimit": args.backoff_limit,
                        "template": {
                            "spec": {
                                "restartPolicy": args.restart_policy,
                                "containers": [{
                                    "name": args.name,
                                    "image": args.image,
                                }]
                            }
                        }
                    }
                }
            }
        }

        # Add command if specified
        if args.command:
            cronjob_spec["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["command"] = args.command

        # Add starting deadline if specified
        if args.starting_deadline:
            cronjob_spec["spec"]["startingDeadlineSeconds"] = args.starting_deadline

        # Apply
        self.apply_manifest(cronjob_spec)
        Logger.success(f"CronJob {args.name} created")

    def apply_manifest(self, manifest: Dict):
        """Apply manifest"""
        import tempfile
        import yaml

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(manifest, f)
            temp_file = f.name

        try:
            self.kube.run(["apply", "-f", temp_file], capture_output=False)
        finally:
            Path(temp_file).unlink()

    def run_job(self, args):
        """Run a job (create and optionally wait)"""
        if args.from_cronjob:
            self.run_from_cronjob(args)
        else:
            self.create_job(args)

    def run_from_cronjob(self, args):
        """Create job from CronJob"""
        if not args.from_cronjob:
            Logger.error("--from-cronjob required")
            return

        Logger.info(f"Creating job from CronJob {args.from_cronjob}...")

        result = self.kube.run([
            "create", "job",
            f"--from=cronjob/{args.from_cronjob}",
            args.name or f"{args.from_cronjob}-manual-{int(time.time())}",
            "-n", self.kube.namespace
        ], capture_output=False)

        if args.wait:
            self.wait_for_job(args.name, args.timeout)

    def delete_job(self, args):
        """Delete a job or cronjob"""
        if not args.name:
            Logger.error("Job name required")
            return

        # Try both job and cronjob
        for resource_type in ["job", "cronjob"]:
            result = self.kube.run([
                "delete", resource_type, args.name,
                "-n", self.kube.namespace
            ], check=False)

            if result.returncode == 0:
                Logger.success(f"Deleted {resource_type}/{args.name}")
                return

        Logger.error(f"Resource {args.name} not found")

    def show_logs(self, args):
        """Show logs from job pods"""
        if not args.name:
            Logger.error("Job name required")
            return

        # Get pods for this job
        result = self.kube.run([
            "get", "pods",
            "-n", self.kube.namespace,
            "-l", f"job-name={args.name}",
            "-o", "jsonpath={.items[*].metadata.name}"
        ])

        pods = result.stdout.split()

        if not pods:
            Logger.error(f"No pods found for job {args.name}")
            return

        for pod in pods:
            print(f"\n{Colors.BOLD}=== Logs from {pod} ==={Colors.RESET}")

            cmd = ["logs", pod, "-n", self.kube.namespace]
            if args.follow:
                cmd.append("--follow")

            self.kube.run(cmd, capture_output=False)

    def show_status(self, args):
        """Show detailed job status"""
        if not args.name:
            Logger.error("Job name required")
            return

        self.kube.run([
            "describe", "job", args.name,
            "-n", self.kube.namespace
        ], capture_output=False)

    def suspend_cronjob(self, args):
        """Suspend a CronJob"""
        if not args.name:
            Logger.error("CronJob name required")
            return

        self.kube.run([
            "patch", "cronjob", args.name,
            "-n", self.kube.namespace,
            "-p", '{"spec":{"suspend":true}}'
        ], capture_output=False)

        Logger.success(f"CronJob {args.name} suspended")

    def resume_cronjob(self, args):
        """Resume a CronJob"""
        if not args.name:
            Logger.error("CronJob name required")
            return

        self.kube.run([
            "patch", "cronjob", args.name,
            "-n", self.kube.namespace,
            "-p", '{"spec":{"suspend":false}}'
        ], capture_output=False)

        Logger.success(f"CronJob {args.name} resumed")

    def show_history(self, args):
        """Show job history for a CronJob"""
        if not args.name:
            Logger.error("CronJob name required")
            return

        # Get jobs created by this CronJob
        result = self.kube.run([
            "get", "jobs",
            "-n", self.kube.namespace,
            "-o", "json"
        ])

        data = json.loads(result.stdout)

        jobs = []
        for item in data.get('items', []):
            owner_refs = item['metadata'].get('ownerReferences', [])
            for ref in owner_refs:
                if ref.get('kind') == 'CronJob' and ref.get('name') == args.name:
                    status = item.get('status', {})
                    jobs.append({
                        'name': item['metadata']['name'],
                        'status': self.get_job_status(status),
                        'duration': self.get_duration(status),
                        'age': self.get_age(item['metadata'].get('creationTimestamp', ''))
                    })

        if not jobs:
            print(f"No jobs found for CronJob {args.name}")
            return

        print(f"\n{Colors.BOLD}Job History for {args.name}{Colors.RESET}")
        self.display_jobs(jobs)

    def cleanup_jobs(self, args):
        """Cleanup old jobs"""
        Logger.info("Finding jobs to cleanup...")

        jobs = self.get_jobs(
            type('Args', (), {'selector': None, 'show_controlled': True, 'status': 'all'})())

        to_delete = []

        for job in jobs:
            should_delete = False

            # Filter by age
            if args.older_than:
                age_limit = self.parse_duration(args.older_than)
                created = job['raw']['metadata'].get('creationTimestamp', '')
                if created:
                    created_dt = datetime.fromisoformat(
                        created.replace('Z', '+00:00'))
                    if datetime.now(created_dt.tzinfo) - created_dt > age_limit:
                        should_delete = True

            # Filter by status (only completed jobs)
            if job['status'] in ['Succeeded', 'Failed']:
                if not args.older_than:  # If no age filter, delete all completed
                    should_delete = True

            if should_delete:
                to_delete.append(job['name'])

        # Keep last N if specified
        if args.keep_last and len(to_delete) > args.keep_last:
            # Sort by age and keep newest
            to_delete = sorted(to_delete)[:-args.keep_last]

        if not to_delete:
            Logger.info("No jobs to cleanup")
            return

        print(f"\n{Colors.YELLOW}Jobs to delete:{Colors.RESET}")
        for name in to_delete:
            print(f"  • {name}")

        if args.dry_run:
            Logger.info("Dry run - no jobs deleted")
            return

        # Confirm
        print()
        response = input(
            f"Delete {len(to_delete)} job(s)? [y/N]: ").strip().lower()

        if response not in ['y', 'yes']:
            Logger.info("Cancelled")
            return

        # Delete
        for name in to_delete:
            self.kube.run([
                "delete", "job", name,
                "-n", self.kube.namespace
            ], check=False, capture_output=True)

        Logger.success(f"Deleted {len(to_delete)} job(s)")

    def parse_duration(self, duration_str: str) -> timedelta:
        """Parse duration string (e.g., 7d, 24h, 30m)"""
        import re
        match = re.match(r'(\d+)([dhm])', duration_str.lower())

        if not match:
            return timedelta(days=7)  # Default

        value, unit = match.groups()
        value = int(value)

        if unit == 'd':
            return timedelta(days=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'm':
            return timedelta(minutes=value)

        return timedelta(days=7)

    def wait_for_job(self, name: str, timeout: int):
        """Wait for job to complete"""
        Logger.info(
            f"Waiting for job {name} to complete (timeout: {timeout}s)...")

        result = self.kube.run([
            "wait", "--for=condition=complete",
            "--timeout", f"{timeout}s",
            f"job/{name}",
            "-n", self.kube.namespace
        ], check=False)

        if result.returncode == 0:
            Logger.success("Job completed successfully")
        else:
            Logger.error("Job did not complete within timeout")

    def watch_jobs(self, args):
        """Watch jobs in real-time"""
        Logger.info("Watching jobs (Ctrl+C to stop)...")

        try:
            while True:
                print("\033[2J\033[H")  # Clear screen
                self.list_jobs(args)
                time.sleep(args.timeout if hasattr(args, 'timeout') else 2)
        except KeyboardInterrupt:
            print("\nStopped watching")


# Usage examples
"""
# List all jobs and cronjobs
python k8s-mgr.py jobs list

# List only jobs
python k8s-mgr.py jobs list --type=job

# List only cronjobs
python k8s-mgr.py jobs list --type=cronjob

# List with status filter
python k8s-mgr.py jobs list --status=failed

# Show jobs created by cronjobs
python k8s-mgr.py jobs list --show-controlled

# Create a simple job
python k8s-mgr.py jobs create my-job --image=busybox --command echo "Hello"

# Create a job with options
python k8s-mgr.py jobs create batch-job \\
  --image=python:3.9 \\
  --command python -c "print('Processing...')" \\
  --completions=5 \\
  --parallelism=2 \\
  --backoff-limit=3 \\
  --ttl-seconds=3600

# Create a CronJob
python k8s-mgr.py jobs create daily-backup \\
  --image=backup:latest \\
  --schedule="0 2 * * *" \\
  --command backup.sh

# Create suspended CronJob
python k8s-mgr.py jobs create maintenance \\
  --image=maintenance:latest \\
  --schedule="0 3 * * 0" \\
  --suspend

# Run job from CronJob
python k8s-mgr.py jobs run manual-backup --from-cronjob=daily-backup

# Run and wait for completion
python k8s-mgr.py jobs run test-job \\
  --image=test:latest \\
  --wait \\
  --timeout=600

# Show logs
python k8s-mgr.py jobs logs my-job

# Follow logs
python k8s-mgr.py jobs logs my-job --follow

# Show status
python k8s-mgr.py jobs status my-job

# Suspend CronJob
python k8s-mgr.py jobs suspend daily-backup

# Resume CronJob
python k8s-mgr.py jobs resume daily-backup

# Show CronJob history
python k8s-mgr.py jobs history daily-backup

# Delete job
python k8s-mgr.py jobs delete my-job

# Cleanup old jobs
python k8s-mgr.py jobs cleanup --older-than=7d

# Cleanup keeping last 5
python k8s-mgr.py jobs cleanup --keep-last=5

# Dry run cleanup
python k8s-mgr.py jobs cleanup --older-than=7d --dry-run

# Watch jobs
python k8s-mgr.py jobs list --watch
"""
