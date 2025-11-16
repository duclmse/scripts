"""Check accessibility of all repositories"""

from core.decorators import Command
from core.logger import Logger


@Command.register("check", help="Check accessibility of all repositories")
class CheckCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        Logger.info(f"Checking accessibility of {self.git.stats.total} repositories")

        for config in self.git.repos:
            repo_url = f"{self.git.remotes.get('origin', '')}/{config.repo}"
            Logger.info(f"Checking {config.repo}...")
            success, _ = self.git.run(['git', 'ls-remote', repo_url], retry=False)
            if success:
                Logger.success(f"✓ {config.repo} is accessible")
                self.git.stats.success += 1
            else:
                Logger.error(f"✗ {config.repo} is NOT accessible")
                self.git.stats.failed += 1

        self.git.stats.print_summary()
