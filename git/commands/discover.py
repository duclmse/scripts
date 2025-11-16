"""Discover git repositories in a directory and generate config"""

import os
import re
from datetime import datetime
from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("discover", aliases=["d"], help="Discover repos in folder and generate config", args=[
    arg("scan_dir", nargs="?", default=".", help="Directory to scan (default: current)"),
    arg("-o", "--output", default="repos-discovered.txt", help="Output config file"),
])
class DiscoverCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        scan_dir = args.scan_dir
        output = args.output
        Logger.info(f"Discovering repositories in: {scan_dir}")

        repos_found = []
        for root, dirs, _ in os.walk(scan_dir):
            if '.git' not in dirs:
                continue
            repo_dir = Path(root)
            _, remote_url = self.git.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=str(repo_dir), retry=False)
            _, branch = self.git.run(
                ['git', 'branch', '--show-current'],
                cwd=str(repo_dir), retry=False)

            if remote_url:
                repo_path = re.sub(r'\.git$', '', remote_url.strip())
                repo_path = re.sub(r'^.*[:/]([^/]+/[^/]+)$', r'\1', repo_path)
                repos_found.append((repo_path, repo_dir.name, branch.strip() or 'main'))

            dirs.remove('.git')

        with open(output, 'w') as f:
            f.write("# Auto-generated repository configuration\n")
            f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write('REMOTE = {\n    "origin": "https://github.com/username",\n}\n\n')
            f.write("repos = [\n")
            for repo_path, repo_name, branch in repos_found:
                f.write(f'    "{repo_path} {repo_name} {branch}",\n')
            f.write("]\n")

        Logger.success(f"Discovered {len(repos_found)} repositories. Config saved to: {output}")
