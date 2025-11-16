"""Remove a repository from the config file"""

from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("remove", aliases=["rm"], help="Remove repository from config", args=[
    arg("repository", help="Repository path to remove"),
])
class RemoveCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        config_file = self.git.config_file
        if not Path(config_file).exists():
            Logger.error(f"Config file '{config_file}' not found!")
            return

        with open(config_file, 'r') as f:
            lines = f.readlines()

        new_lines = []
        removed = False
        for line in lines:
            if f'"{args.repository}' in line and 'repos = [' not in line:
                removed = True
            else:
                new_lines.append(line)

        if not removed:
            Logger.warn(f"Repository {args.repository} not found in config")
            return

        with open(config_file, 'w') as f:
            f.writelines(new_lines)
        Logger.success(f"Removed {args.repository} from config")
