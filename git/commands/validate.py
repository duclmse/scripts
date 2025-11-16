"""Validate repositories are clean and in sync with remote"""

from pathlib import Path

from core.decorators import Command
from core.logger import Logger


@Command.register("validate", aliases=["v"], help="Validate repositories are in sync")
class ValidateCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        Logger.info(f"Validating {self.git.stats.total} repositories")

        for config in self.git.repos:
            target = config.target_folder
            if not Path(target).exists():
                Logger.warn(f"✗ {config.repo} - Not cloned")
                self.git.stats.failed += 1
                continue

            _, status = self.git.run(['git', 'status', '--porcelain'], cwd=target, retry=False)
            if status.strip():
                Logger.warn(f"● {config.repo} - Has uncommitted changes")
                self.git.stats.failed += 1
                continue

            self.git.run(['git', 'fetch'], cwd=target, retry=False)
            ok, ahead_behind = self.git.run(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{u}'],
                cwd=target, retry=False)

            if ok and ahead_behind.strip():
                behind, ahead = ahead_behind.strip().split()
                if int(behind) > 0 or int(ahead) > 0:
                    Logger.warn(f"↕ {config.repo} - Out of sync (↓{behind} ↑{ahead})")
                    self.git.stats.failed += 1
                    continue

            Logger.success(f"✓ {config.repo} - Valid")
            self.git.stats.success += 1

        self.git.stats.print_summary()
