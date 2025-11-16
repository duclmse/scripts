"""Import repositories from GitLab (not yet implemented)"""

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("import-gitlab", help="Import repos from GitLab user/org", args=[
    arg("username", help="GitLab username or organization"),
    arg("--private", action="store_true", help="Include private repositories"),
    arg("-o", "--output", default="repos-gitlab.txt", help="Output config file"),
    arg("--url", default="https://gitlab.com", help="GitLab instance URL"),
])
class ImportGitLabCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        Logger.error("GitLab import not yet implemented")
