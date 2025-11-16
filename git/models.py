"""Data models for the Git Repository Manager"""

from dataclasses import dataclass
from pathlib import Path

from core.colors import Colors
from core.logger import Logger


@dataclass
class RepoConfig:
    """Repository configuration"""
    repo: str
    folder: str | None = None
    branch: str | None = None

    @property
    def target_folder(self) -> str:
        if self.folder:
            return self.folder
        return Path(self.repo).stem.replace('.git', '')


@dataclass
class Statistics:
    """Operation statistics"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0

    def print_summary(self):
        Logger.info("=" * 50)
        Logger.info("Summary:")
        Logger.info(f"{Colors.GREEN}  Successful: {self.success}{Colors.RESET}")
        Logger.info(f"{Colors.RED}  Failed: {self.failed}{Colors.RESET}")
        Logger.info(f"{Colors.YELLOW}  Skipped: {self.skipped}{Colors.RESET}")
        Logger.info(f"  Total: {self.total}")
        Logger.info("=" * 50)
