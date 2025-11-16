"""Show status of all repositories"""

from pathlib import Path

from core.colors import Colors
from core.decorators import Command
from core.logger import Logger


@Command.register("status", aliases=["st"], help="Show status of all repositories")
class StatusCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        Logger.info("Repository Status Report\n")

        for config in self.git.repos:
            target = config.target_folder
            if not Path(target).exists():
                print(f"{Colors.RED}✗{Colors.RESET} {config.repo} - Not cloned")
                continue

            _, branch = self.git.run(['git', 'branch', '--show-current'], cwd=target, retry=False)
            current_branch = branch.strip() or 'unknown'

            _, status = self.git.run(['git', 'status', '--porcelain'], cwd=target, retry=False)

            ok, ahead_behind = self.git.run(
                ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{u}'],
                cwd=target, retry=False
            )

            if status.strip():
                print(f"{Colors.YELLOW}●{Colors.RESET} {config.repo} - Modified (branch: {current_branch})")
            elif ok and ahead_behind.strip():
                behind, ahead = ahead_behind.strip().split()
                if int(behind) > 0 or int(ahead) > 0:
                    print(f"{Colors.YELLOW}↕{Colors.RESET} {config.repo} - Out of sync (↓{behind} ↑{ahead}, branch: {current_branch})")
                else:
                    print(f"{Colors.GREEN}✓{Colors.RESET} {config.repo} - Clean (branch: {current_branch})")
            else:
                print(f"{Colors.GREEN}✓{Colors.RESET} {config.repo} - Clean (branch: {current_branch})")
