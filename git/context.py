"""GitContext — shared execution environment passed to every git command"""

import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from core.logger import Logger
from git.models import RepoConfig, Statistics


class GitContext:
    """
    Shared state and infrastructure for all git commands.
    Analogous to KubeCommand in the k8s module.
    """

    VERSION = "2.0.0"

    def __init__(self, args):
        self.config_file    = args.file
        self.dry_run        = args.dry_run
        self.parallel_jobs  = args.parallel
        self.skip_existing  = args.skip_existing
        self.force          = args.force
        self.interactive    = args.interactive
        self.retry_count    = args.retry
        self.timeout        = args.timeout
        self.include_pattern = args.include
        self.exclude_pattern = args.exclude
        self.use_ssh        = args.ssh
        self.submodules     = args.submodules
        self.mirror         = args.mirror
        self.bare           = args.bare
        self.verbose        = args.verbose

        self.remotes: dict[str, str] = {}
        self.repos: list[RepoConfig] = []
        self.stats = Statistics()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def check_dependencies(self):
        if not shutil.which('git'):
            Logger.error("git is not installed. Please install it first.")
            sys.exit(1)

    def load_config(self):
        config_path = Path(self.config_file)
        if not config_path.exists():
            Logger.error(f"Config file '{self.config_file}' not found!")
            sys.exit(1)

        try:
            config_globals: dict = {}
            with open(config_path, 'r') as f:
                exec(f.read(), config_globals)

            self.remotes = config_globals.get('REMOTE', {})

            for repo_line in config_globals.get('repos', []):
                parts = repo_line.split()
                if parts:
                    self.repos.append(RepoConfig(
                        repo=parts[0],
                        folder=parts[1] if len(parts) > 1 else None,
                        branch=parts[2] if len(parts) > 2 else None,
                    ))

            self.stats.total = len(self.repos)
            Logger.info(f"Loaded {self.stats.total} repositories from config")

        except Exception as e:
            Logger.error(f"Error loading config: {e}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Helpers available to all commands
    # ------------------------------------------------------------------

    def should_process(self, repo: str) -> bool:
        if self.include_pattern and not re.search(self.include_pattern, repo):
            return False
        if self.exclude_pattern and re.search(self.exclude_pattern, repo):
            return False
        return True

    def convert_url(self, url: str) -> str:
        if self.use_ssh and url.startswith('https://'):
            parsed = urlparse(url)
            return f"git@{parsed.netloc}:{parsed.path.lstrip('/')}"
        return url

    def run(self, cmd: list[str], cwd: str | None = None, retry: bool = True) -> tuple[bool, str]:
        """Execute a shell command with optional retry. Returns (success, stdout)."""
        attempts = self.retry_count if retry else 1

        for attempt in range(1, attempts + 1):
            if attempt > 1:
                Logger.warn(f"Retry attempt {attempt}/{attempts}")
                time.sleep(2)

            try:
                if self.dry_run:
                    Logger.info(f"DRY RUN: {' '.join(cmd)}")
                    return True, ""

                result = subprocess.run(
                    cmd, cwd=cwd, capture_output=True, text=True, timeout=self.timeout
                )
                if result.returncode == 0:
                    return True, result.stdout
                if attempt == attempts:
                    Logger.debug(f"Command failed: {result.stderr.strip()}")

            except subprocess.TimeoutExpired:
                Logger.error(f"Command timed out after {self.timeout}s")
                if attempt == attempts:
                    return False, "Timeout"
            except Exception as e:
                Logger.error(f"Command execution error: {e}")
                if attempt == attempts:
                    return False, str(e)

        return False, "Max retries reached"

    # ------------------------------------------------------------------
    # Parallel / sequential repo runners
    # ------------------------------------------------------------------

    def run_parallel(self, operation, *args):
        with ThreadPoolExecutor(max_workers=self.parallel_jobs) as executor:
            futures = [
                executor.submit(operation, config, *args, i)
                for i, config in enumerate(self.repos, 1)
            ]
            for future in as_completed(futures):
                self._tally(future.result())

    def run_sequential(self, operation, *args):
        for i, config in enumerate(self.repos, 1):
            self._tally(operation(config, *args, i))

    def run_all(self, operation, *args):
        """Dispatch to parallel or sequential based on --parallel flag."""
        if self.parallel_jobs > 1:
            self.run_parallel(operation, *args)
        else:
            self.run_sequential(operation, *args)

    def _tally(self, result):
        if result is True:
            self.stats.success += 1
        elif result is False:
            self.stats.skipped += 1
        else:
            self.stats.failed += 1
