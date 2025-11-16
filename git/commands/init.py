"""Create a template config file"""

from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("init", help="Create template config file", args=[
    arg("-o", "--output", default="repos.txt", help="Output config file"),
])
class InitCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        output = args.output
        if Path(output).exists() and not self.git.force:
            Logger.error(f"'{output}' already exists. Use --force to overwrite.")
            return

        template = '''\
# Git Repository Manager Configuration
# Format: "repository folder branch"

REMOTE = {
    "origin": "https://github.com/username",
    "gitlab": "https://gitlab.com/username",
    "bitbucket": "https://bitbucket.org/username",
}

repos = [
    "user/repo1 repo1 main",
    "user/repo2 custom-folder develop",
    "user/repo3",
]
'''
        with open(output, 'w') as f:
            f.write(template)
        Logger.success(f"Template config created: {output}")
