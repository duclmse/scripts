"""Add a repository to the config file"""

from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("add", help="Add repository to config", args=[
    arg("repository", help="Repository path (e.g., user/repo)"),
    arg("--folder", "-f", help="Local folder name"),
    arg("--branch", "-b", help="Branch name"),
])
class AddCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        config_file = self.git.config_file
        if not Path(config_file).exists():
            Logger.error(f"Config file '{config_file}' not found!")
            return

        with open(config_file, 'r') as f:
            content = f.read()

        if 'repos = [' not in content:
            Logger.error("Invalid config file format")
            return

        repo_line = f'    "{args.repository}'
        if args.folder:
            repo_line += f' {args.folder}'
        if args.branch:
            repo_line += f' {args.branch}'
        repo_line += '",\n'

        content = content.replace('repos = [', f'repos = [\n{repo_line}', 1)
        with open(config_file, 'w') as f:
            f.write(content)
        Logger.success(f"Added {args.repository} to config")
