"""Clone repositories from config"""

import shutil
from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger
from git.models import RepoConfig


@Command.register("clone", aliases=["c"], help="Clone repositories from config file", args=[
    arg("-r", "--remote", default="origin", help="Remote name (default: origin)"),
    arg("-d", "--depth", type=int, help="Shallow clone depth"),
])
class CloneCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        remote = args.remote
        depth = args.depth
        Logger.info(f"Starting clone operation for {self.git.stats.total} repositories")
        self.git.run_all(self._clone_one, remote, depth)
        self.git.stats.print_summary()

    def _clone_one(self, config: RepoConfig, remote: str, depth: int | None, current: int) -> bool | None:
        repo = config.repo
        target = config.target_folder

        if not self.git.should_process(repo):
            Logger.info(f"[{current}/{self.git.stats.total}] Skipping {repo} (filtered)")
            return False

        if self.git.interactive:
            response = input(f"Clone {repo}? [Y/n] ").strip().lower()
            if response and response != 'y':
                return False

        Logger.info(f"[{current}/{self.git.stats.total}] Cloning {repo}")

        if Path(target).exists():
            if self.git.skip_existing:
                Logger.warn(f"'{target}' exists, skipping")
                return False
            elif not self.git.force:
                Logger.error(f"'{target}' exists. Use --force or --skip-existing")
                return None
            else:
                Logger.warn(f"Removing existing '{target}'")
                if not self.git.dry_run:
                    shutil.rmtree(target)

        repo_url = self.git.convert_url(f"{self.git.remotes.get(remote, remote)}/{repo}")

        cmd = ['git', 'clone']
        if depth:
            cmd.extend(['--depth', str(depth)])
        if config.branch:
            cmd.extend(['-b', config.branch])
        if self.git.submodules:
            cmd.append('--recurse-submodules')
        if self.git.mirror:
            cmd.append('--mirror')
        if self.git.bare:
            cmd.append('--bare')
        cmd.extend([repo_url, target])

        success, _ = self.git.run(cmd)
        if success:
            Logger.success(f"Cloned {repo}")
            return True
        Logger.error(f"Failed to clone {repo}")
        return None
