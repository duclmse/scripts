"""Import repositories from GitHub"""

import json
import urllib.request
from datetime import datetime

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("import-github", help="Import repos from GitHub user/org", args=[
    arg("username", help="GitHub username or organization"),
    arg("--private", action="store_true", help="Include private repositories (requires auth token)"),
    arg("-o", "--output", default="repos-github.txt", help="Output config file"),
])
class ImportGitHubCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        username = args.username
        Logger.info(f"Importing repositories from GitHub user/org: {username}")

        try:
            api_url = (
                "https://api.github.com/user/repos?per_page=100"
                if args.private
                else f"https://api.github.com/users/{username}/repos?per_page=100"
            )
            req = urllib.request.Request(api_url)
            req.add_header('Accept', 'application/vnd.github.v3+json')

            with urllib.request.urlopen(req) as response:
                repos_data = json.loads(response.read())

            with open(args.output, 'w') as f:
                f.write(f"# GitHub repositories for {username}\n")
                f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f'REMOTE = {{\n    "origin": "https://github.com/{username}",\n}}\n\n')
                f.write("repos = [\n")
                for repo in repos_data:
                    f.write(f'    "{repo["full_name"]} {repo["name"]} {repo.get("default_branch", "main")}",\n')
                f.write("]\n")

            Logger.success(f"GitHub import complete. Config saved to: {args.output}")
            Logger.info(f"Imported {len(repos_data)} repositories")
        except Exception as e:
            Logger.error(f"GitHub import failed: {e}")
