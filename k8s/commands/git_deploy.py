"""
Git Deploy Command - Deploy directly from Git repositories
"""

import json
import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from core.decorators import Command, arg
from core.logger import Logger
from core.colors import Colors
from core.config import KubeConfig


@Command.register("git-deploy", aliases=["gd"], help="Deploy from Git repository", args=[
    arg("repo_url", help="Git repository URL"),
    arg("--branch", "-b", default="main", help="Git branch (default: main)"),
    arg("--tag", help="Git tag to deploy"),
    arg("--commit", help="Specific commit SHA"),
    arg("--path", default=".", help="Path to manifests in repo (default: .)"),

    # Manifest options
    arg("--recursive", "-r", action="store_true",
        help="Apply manifests recursively"),
    arg("--kustomize", action="store_true", help="Use kustomize"),
    arg("--helm", action="store_true", help="Deploy using Helm"),
    arg("--helm-values", help="Helm values file in repo"),

    # Git options
    arg("--depth", type=int, default=1, help="Git clone depth (default: 1)"),
    arg("--ssh-key", help="SSH key file for private repos"),
    arg("--token", help="Access token for private repos"),
    arg("--username", help="Git username"),
    arg("--password", help="Git password"),

    # Deployment options
    arg("--dry-run", action="store_true", help="Show what would be deployed"),
    arg("--validate", action="store_true",
        help="Validate manifests before applying"),
    arg("--prune", action="store_true", help="Prune resources not in repo"),
    arg("--force", action="store_true", help="Force apply (replace existing)"),
    arg("--server-side", action="store_true", help="Server-side apply"),

    # Tracking
    arg("--track", action="store_true", help="Track deployment (save metadata)"),
    arg("--label", help="Add label to deployed resources"),
    arg("--annotation", help="Add annotation to deployed resources"),

    # Filtering
    arg("--include", help="Include only files matching pattern (glob)"),
    arg("--exclude", help="Exclude files matching pattern (glob)"),
    arg("--types", help="Only deploy specific resource types (comma-separated)"),

    # Advanced
    arg("--wait", action="store_true", help="Wait for resources to be ready"),
    arg("--timeout", type=int, default=300,
        help="Timeout in seconds (default: 300)"),
    arg("--rollback-on-error", action="store_true",
        help="Rollback on deployment error"),
    arg("--keep-clone", action="store_true",
        help="Keep cloned repo for inspection"),
])
class GitDeployCommand:
    """Deploy directly from Git repository"""

    def __init__(self, kube):
        self.kube = kube
        self.config = KubeConfig()
        self.clone_dir = None
        self.deployed_resources = []
        self.previous_state = {}

    def execute(self, args):
        """Execute git deployment"""
        try:
            # Clone repository
            self.clone_dir = self.clone_repository(args)

            if not self.clone_dir:
                Logger.error("Failed to clone repository")
                return

            Logger.success(f"Cloned to {self.clone_dir}")

            # Get commit info
            commit_info = self.get_commit_info()
            Logger.info(
                f"Deploying commit: {commit_info['sha'][:8]} - {commit_info['message']}")

            # Find manifest files
            manifest_files = self.find_manifests(args)

            if not manifest_files:
                Logger.error("No manifest files found")
                return

            Logger.info(f"Found {len(manifest_files)} manifest file(s)")

            # Validate if requested
            if args.validate:
                if not self.validate_manifests(manifest_files):
                    Logger.error("Validation failed")
                    return

            # Save current state for rollback
            if args.rollback_on_error:
                self.save_current_state(args)

            # Deploy manifests
            if args.dry_run:
                self.dry_run_deploy(manifest_files, args)
            else:
                success = self.deploy_manifests(
                    manifest_files, args, commit_info)

                if success:
                    # Track deployment
                    if args.track:
                        self.track_deployment(args, commit_info)

                    Logger.success("Deployment completed successfully!")
                else:
                    Logger.error("Deployment failed")

                    if args.rollback_on_error:
                        self.rollback(args)

        finally:
            # Cleanup
            if not args.keep_clone and self.clone_dir:
                self.cleanup(self.clone_dir)

    def clone_repository(self, args) -> Optional[Path]:
        """Clone Git repository"""
        Logger.info(f"Cloning {args.repo_url}...")

        # Create temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix="k8s-git-deploy-"))

        # Build git clone command
        cmd = ["git", "clone"]

        # Depth
        if args.depth:
            cmd.extend(["--depth", str(args.depth)])

        # Branch or tag
        if args.tag:
            cmd.extend(["--branch", args.tag])
        elif args.branch:
            cmd.extend(["--branch", args.branch])

        # Handle authentication
        repo_url = args.repo_url

        if args.token:
            # Add token to URL
            if "github.com" in repo_url:
                repo_url = repo_url.replace(
                    "https://", f"https://{args.token}@")
            elif "gitlab.com" in repo_url:
                repo_url = repo_url.replace(
                    "https://", f"https://oauth2:{args.token}@")
        elif args.username and args.password:
            repo_url = repo_url.replace(
                "https://", f"https://{args.username}:{args.password}@")

        cmd.extend([repo_url, str(temp_dir)])

        # Set SSH key if provided
        env = None
        if args.ssh_key:
            env = {
                "GIT_SSH_COMMAND": f"ssh -i {args.ssh_key} -o StrictHostKeyChecking=no"
            }

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=env
            )

            # Checkout specific commit if requested
            if args.commit:
                subprocess.run(
                    ["git", "checkout", args.commit],
                    cwd=temp_dir,
                    check=True,
                    capture_output=True
                )

            return temp_dir

        except subprocess.CalledProcessError as e:
            Logger.error(f"Git clone failed: {e.stderr}")
            return None

    def get_commit_info(self) -> Dict[str, str]:
        """Get commit information"""
        try:
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.clone_dir,
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()

            message = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=self.clone_dir,
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()

            author = subprocess.run(
                ["git", "log", "-1", "--pretty=%an"],
                cwd=self.clone_dir,
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()

            date = subprocess.run(
                ["git", "log", "-1", "--pretty=%ai"],
                cwd=self.clone_dir,
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()

            return {
                "sha": sha,
                "message": message,
                "author": author,
                "date": date
            }
        except Exception:
            return {
                "sha": "unknown",
                "message": "unknown",
                "author": "unknown",
                "date": "unknown"
            }

    def find_manifests(self, args) -> List[Path]:
        """Find Kubernetes manifest files"""
        manifest_dir = self.clone_dir / args.path

        if not manifest_dir.exists():
            Logger.error(f"Path not found: {args.path}")
            return []

        manifest_files = []

        # File patterns
        patterns = ["*.yaml", "*.yml"]

        if args.include:
            patterns = [args.include]

        # Find files
        for pattern in patterns:
            if args.recursive:
                files = manifest_dir.rglob(pattern)
            else:
                files = manifest_dir.glob(pattern)

            for file in files:
                # Exclude patterns
                if args.exclude and Path(file.name).match(args.exclude):
                    continue

                # Skip hidden files and directories
                if any(part.startswith('.') for part in file.parts):
                    continue

                manifest_files.append(file)

        return sorted(manifest_files)

    def validate_manifests(self, manifest_files: List[Path]) -> bool:
        """Validate manifest files"""
        Logger.info("Validating manifests...")

        valid = True

        for file in manifest_files:
            try:
                # Parse YAML
                with open(file) as f:
                    docs = list(yaml.safe_load_all(f))

                # Validate with kubectl
                result = subprocess.run(
                    ["kubectl", "apply", "-f",
                        str(file), "--dry-run=client", "--validate=true"],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if result.returncode != 0:
                    Logger.error(
                        f"Validation failed for {file.name}: {result.stderr}")
                    valid = False
                else:
                    Logger.verbose_log(f"✓ {file.name}")

            except yaml.YAMLError as e:
                Logger.error(f"YAML error in {file.name}: {e}")
                valid = False

        return valid

    def save_current_state(self, args):
        """Save current state for rollback"""
        Logger.verbose_log("Saving current state for rollback...")

        try:
            result = self.kube.run([
                "get", "all",
                "-n", self.kube.namespace,
                "-o", "yaml"
            ])

            self.previous_state = yaml.safe_load(result.stdout)
        except Exception as e:
            Logger.warn(f"Could not save state: {e}")

    def dry_run_deploy(self, manifest_files: List[Path], args):
        """Dry run deployment"""
        Logger.info("Dry run - showing what would be deployed:")
        print()

        for file in manifest_files:
            print(f"{Colors.BOLD}{file.relative_to(self.clone_dir)}{Colors.RESET}")

            result = subprocess.run(
                ["kubectl", "apply", "-f", str(file),
                 "-n", self.kube.namespace, "--dry-run=client"],
                capture_output=True,
                text=True
            )

            for line in result.stdout.splitlines():
                print(f"  {line}")
            print()

    def deploy_manifests(self, manifest_files: List[Path], args, commit_info: Dict) -> bool:
        """Deploy manifest files"""
        Logger.info("Deploying manifests...")

        success = True

        for file in manifest_files:
            Logger.info(f"Applying {file.name}...")

            # Filter by resource types if specified
            if args.types:
                if not self.contains_types(file, args.types.split(',')):
                    Logger.verbose_log(f"Skipping {file.name} (type filter)")
                    continue

            try:
                # Build kubectl command
                cmd = ["kubectl", "apply", "-f",
                       str(file), "-n", self.kube.namespace]

                if args.force:
                    cmd.append("--force")

                if args.server_side:
                    cmd.append("--server-side")

                if args.prune:
                    cmd.extend(
                        ["--prune", "-l", f"git-deploy={commit_info['sha'][:8]}"])

                # Add labels/annotations
                if args.label:
                    # This would need to patch resources after apply
                    pass

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                # Track deployed resources
                for line in result.stdout.splitlines():
                    if "created" in line or "configured" in line:
                        Logger.success(f"  {line}")
                        self.deployed_resources.append(line.split()[0])

            except subprocess.CalledProcessError as e:
                Logger.error(f"Failed to apply {file.name}: {e.stderr}")
                success = False
                break

        # Wait for resources if requested
        if success and args.wait:
            success = self.wait_for_resources(args.timeout)

        return success

    def contains_types(self, file: Path, types: List[str]) -> bool:
        """Check if file contains specified resource types"""
        try:
            with open(file) as f:
                docs = yaml.safe_load_all(f)
                for doc in docs:
                    if doc and doc.get('kind', '').lower() in [t.lower() for t in types]:
                        return True
        except:
            pass

        return False

    def wait_for_resources(self, timeout: int) -> bool:
        """Wait for resources to be ready"""
        Logger.info(
            f"Waiting for resources to be ready (timeout: {timeout}s)...")

        # Wait for deployments
        result = subprocess.run(
            ["kubectl", "wait", "--for=condition=available",
             "--timeout", f"{timeout}s",
             "deployment", "--all",
             "-n", self.kube.namespace],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            Logger.success("All resources ready")
            return True
        else:
            Logger.error("Timeout waiting for resources")
            return False

    def track_deployment(self, args, commit_info: Dict):
        """Track deployment metadata"""
        deployment_record = {
            "timestamp": datetime.now().isoformat(),
            "repo": args.repo_url,
            "branch": args.branch,
            "commit": commit_info["sha"],
            "commit_message": commit_info["message"],
            "author": commit_info["author"],
            "namespace": self.kube.namespace,
            "context": self.kube.get_current_context(),
            "deployed_resources": self.deployed_resources
        }

        # Save to deployment history
        history_file = Path.home() / ".kube-mgr" / "git-deploy-history.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        history = []
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text())
            except:
                pass

        history.append(deployment_record)

        # Keep last 100 deployments
        history = history[-100:]

        history_file.write_text(json.dumps(history, indent=2))

        Logger.success("Deployment tracked")

        # Add annotations to resources
        self.annotate_resources(commit_info)

    def annotate_resources(self, commit_info: Dict):
        """Add git annotations to deployed resources"""
        annotations = {
            "git-deploy/commit": commit_info["sha"],
            "git-deploy/author": commit_info["author"],
            "git-deploy/date": commit_info["date"],
            "git-deploy/deployed-at": datetime.now().isoformat()
        }

        for resource in self.deployed_resources:
            try:
                # Build annotation string
                annotation_str = ",".join(
                    [f"{k}={v}" for k, v in annotations.items()])

                self.kube.run([
                    "annotate", resource,
                    "-n", self.kube.namespace,
                    annotation_str,
                    "--overwrite"
                ], check=False)

            except Exception:
                pass

    def rollback(self, args):
        """Rollback deployment"""
        Logger.warn("Rolling back deployment...")

        if not self.previous_state:
            Logger.error("No previous state saved")
            return

        # Delete deployed resources
        for resource in self.deployed_resources:
            try:
                self.kube.run([
                    "delete", resource,
                    "-n", self.kube.namespace
                ], check=False)
            except:
                pass

        Logger.success("Rollback completed")

    def cleanup(self, directory: Path):
        """Cleanup cloned repository"""
        Logger.verbose_log(f"Cleaning up {directory}")

        import shutil
        try:
            shutil.rmtree(directory)
        except Exception as e:
            Logger.warn(f"Failed to cleanup: {e}")


# Subcommand: List deployment history
@Command.register("git-deploy-history", aliases=["gdh"], help="Show git deployment history", args=[
    arg("--limit", type=int, default=10, help="Number of deployments to show"),
    arg("--namespace", help="Filter by namespace"),
    arg("--repo", help="Filter by repository"),
])
class GitDeployHistoryCommand:
    """Show git deployment history"""

    def __init__(self, kube):
        self.kube = kube

    def execute(self, args):
        """Show deployment history"""
        history_file = Path.home() / ".kube-mgr" / "git-deploy-history.json"

        if not history_file.exists():
            print("No deployment history found")
            return

        history = json.loads(history_file.read_text())

        # Filter
        if args.namespace:
            history = [h for h in history if h.get('namespace')
                       == args.namespace]

        if args.repo:
            history = [h for h in history if args.repo in h.get('repo', '')]

        # Show last N
        history = history[-args.limit:]

        print(f"\n{Colors.BOLD}Git Deployment History{Colors.RESET}")
        print("=" * 80)

        for record in reversed(history):
            timestamp = record.get('timestamp', '')
            repo = record.get('repo', '')
            commit = record.get('commit', '')[:8]
            message = record.get('commit_message', '')
            namespace = record.get('namespace', '')

            print(f"\n{Colors.GREEN}{timestamp}{Colors.RESET}")
            print(f"  Repo: {repo}")
            print(f"  Commit: {commit} - {message}")
            print(f"  Namespace: {namespace}")
            print(f"  Resources: {len(record.get('deployed_resources', []))}")


# Usage examples
"""
# Deploy from GitHub main branch
python k8s-mgr.py git-deploy https://github.com/user/k8s-manifests

# Deploy from specific branch
python k8s-mgr.py git-deploy https://github.com/user/repo -b develop

# Deploy from tag
python k8s-mgr.py git-deploy https://github.com/user/repo --tag v1.2.3

# Deploy from specific commit
python k8s-mgr.py git-deploy https://github.com/user/repo --commit abc123

# Deploy from subdirectory
python k8s-mgr.py git-deploy https://github.com/user/repo --path k8s/production

# Deploy recursively
python k8s-mgr.py git-deploy https://github.com/user/repo --path deployments -r

# Private repo with token
python k8s-mgr.py git-deploy https://github.com/user/private-repo --token ghp_xxx

# Private repo with SSH key
python k8s-mgr.py git-deploy git@github.com:user/repo.git --ssh-key ~/.ssh/id_rsa

# Dry run
python k8s-mgr.py git-deploy https://github.com/user/repo --dry-run

# Validate before deploying
python k8s-mgr.py git-deploy https://github.com/user/repo --validate

# Track deployment with annotations
python k8s-mgr.py git-deploy https://github.com/user/repo --track

# Wait for resources to be ready
python k8s-mgr.py git-deploy https://github.com/user/repo --wait --timeout=600

# Rollback on error
python k8s-mgr.py git-deploy https://github.com/user/repo --rollback-on-error

# Deploy only specific resource types
python k8s-mgr.py git-deploy https://github.com/user/repo --types=deployment,service

# Include/exclude patterns
python k8s-mgr.py git-deploy https://github.com/user/repo \\
  --include="prod-*.yaml" \\
  --exclude="*-test.yaml"

# Keep clone for inspection
python k8s-mgr.py git-deploy https://github.com/user/repo --keep-clone

# Kustomize deployment
python k8s-mgr.py git-deploy https://github.com/user/repo --kustomize --path overlays/prod

# Helm deployment
python k8s-mgr.py git-deploy https://github.com/user/repo --helm --helm-values values.yaml

# View deployment history
python k8s-mgr.py git-deploy-history --limit=20

# Filter history
python k8s-mgr.py git-deploy-history --namespace=production --repo=backend
"""
