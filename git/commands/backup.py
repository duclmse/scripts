"""Create backup archive of all repositories"""

import tarfile
from datetime import datetime
from pathlib import Path

from core.decorators import Command, arg
from core.logger import Logger


@Command.register("backup", aliases=["b"], help="Create backup archive of all repos", args=[
    arg("-o", "--output", help="Output file name"),
])
class BackupCommand:
    def __init__(self, git):
        self.git = git

    def execute(self, args):
        self.git.load_config()
        output = args.output or f"repos-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.tar.gz"
        Logger.info(f"Creating backup archive: {output}")

        folders = [c.target_folder for c in self.git.repos if Path(c.target_folder).exists()]
        if not folders:
            Logger.error("No repositories found to backup")
            return

        if self.git.dry_run:
            Logger.info(f"DRY RUN: Would backup {len(folders)} repositories to {output}")
            return

        try:
            with tarfile.open(output, "w:gz") as tar:
                for folder in folders:
                    Logger.info(f"Adding {folder}...")
                    tar.add(folder)
            Logger.success(f"Backup created: {output}")
            size_mb = Path(output).stat().st_size / (1024 * 1024)
            Logger.info(f"Archive size: {size_mb:.2f} MB")
        except Exception as e:
            Logger.error(f"Backup failed: {e}")
