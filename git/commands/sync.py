"""Sync repositories (pull + push)"""

from pathlib import Path

from core.decorators import Command
from core.logger import Logger
from git.models import RepoConfig


@Command.register("sync", aliases=["s"], help="Sync repositories (pull + push)")
class SyncCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        Logger.info(f"Starting sync operation for {self.git.stats.total} repositories")
        self.git.run_all(self._sync_one)
        self.git.stats.print_summary()

    def _sync_one(self, config: RepoConfig, current: int) -> bool | None:
        if not self.git.should_process(config.repo):
            return False

        target = config.target_folder
        if not Path(target).exists():
            Logger.warn(f"[{current}/{self.git.stats.total}] '{target}' not found, skipping")
            return False

        Logger.info(f"[{current}/{self.git.stats.total}] Syncing {config.repo}")

        pull_ok, _ = self.git.run(['git', 'pull', '--rebase'], cwd=target)
        if not pull_ok:
            Logger.error(f"Failed to pull {config.repo}")
            return None

        push_ok, _ = self.git.run(['git', 'push'], cwd=target)
        if push_ok:
            Logger.success(f"Synced {config.repo}")
            return True
        Logger.error(f"Failed to push {config.repo}")
        return None
