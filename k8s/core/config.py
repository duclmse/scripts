
"""Configuration management"""
import json
from pathlib import Path
from typing import Any
from .logger import Logger

CONFIG_DIR = Path.home() / ".kube-mgr"
FORWARDS_DB = CONFIG_DIR / "forwards.db"
CONFIG_FILE = CONFIG_DIR / "config.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
TEMPLATES_FILE = CONFIG_DIR / "templates.json"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"
HISTORY_DIR = CONFIG_DIR / "history"

class KubeConfig:
    """Kubernetes configuration management"""

    def __init__(self):
        self.ensure_config_dir()

    @staticmethod
    def ensure_config_dir():
        """Ensure configuration directory exists"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)

        for file, default in [
            (FORWARDS_DB, "[]"),
            (CONFIG_FILE, "{}"),
            (BOOKMARKS_FILE, "{}"),
            (TEMPLATES_FILE, "{}"),
            (FAVORITES_FILE, "{}")
        ]:
            if not file.exists():
                file.write_text(default)

    @staticmethod
    def load_json(filepath: Path) -> Any:
        try:
            return json.loads(filepath.read_text())
        except Exception as e:
            Logger.error(f"Failed to load {filepath}: {e}")
            return {} if filepath.suffix == ".json" else []

    @staticmethod
    def save_json(filepath: Path, data: Any):
        filepath.write_text(json.dumps(data, indent=2))

    def get_forwards(self) -> list:
        return self.load_json(FORWARDS_DB)

    def save_forwards(self, forwards: list):
        self.save_json(FORWARDS_DB, forwards)

    def get_bookmarks(self) -> dict:
        return self.load_json(BOOKMARKS_FILE)

    def save_bookmarks(self, bookmarks: dict):
        self.save_json(BOOKMARKS_FILE, bookmarks)

    def get_templates(self) -> dict:
        return self.load_json(TEMPLATES_FILE)

    def save_templates(self, templates: dict):
        self.save_json(TEMPLATES_FILE, templates)

    def get_favorites(self) -> dict:
        return self.load_json(FAVORITES_FILE)

    def save_favorites(self, favorites: dict):
        self.save_json(FAVORITES_FILE, favorites)
