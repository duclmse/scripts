"""List all configured repositories"""

from pathlib import Path

from core.colors import Colors
from core.decorators import Command
from core.logger import Logger


@Command.register("list", aliases=["ls"], help="List all configured repositories")
class ListCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        print(f"{Colors.BLUE}Configured Repositories:{Colors.RESET}\n")
        for i, config in enumerate(self.git.repos, 1):
            exists = "✓" if Path(config.target_folder).exists() else "✗"
            print(f"{i}. {exists} {config.repo}")
            print(f"   Folder: {config.target_folder}")
            print(f"   Branch: {config.branch or 'default'}\n")
        print(f"Total: {len(self.git.repos)} repositories")
