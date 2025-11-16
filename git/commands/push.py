"""Push repositories to remote"""

from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger
from git.models import RepoConfig


@Command.register("push", aliases=["p"], help="Push repositories to remote", args=[
    arg("-r", "--remote", default="origin", help="Remote name (default: origin)"),
])
class PushCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        Logger.info(f"Starting push operation for {self.git.stats.total} repositories")
        self.git.run_all(self._push_one, args.remote)
        self.git.stats.print_summary()

    def _push_one(self, config: RepoConfig, remote: str, current: int) -> bool | None:
        if not self.git.should_process(config.repo):
            return False

        target = config.target_folder
        if not Path(target).exists():
            Logger.warn(f"[{current}/{self.git.stats.total}] '{target}' not found, skipping")
            return False

        Logger.info(f"[{current}/{self.git.stats.total}] Pushing {config.repo}")
        cmd = ['git', 'push', remote]
        if config.branch:
            cmd.append(config.branch)

        success, _ = self.git.run(cmd, cwd=target)
        if success:
            Logger.success(f"Pushed {config.repo}")
            return True
        Logger.error(f"Failed to push {config.repo}")
        return None
