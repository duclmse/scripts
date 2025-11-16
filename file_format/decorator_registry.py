from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str = ""
    author: str = ""


class PluginRegistry:
    """Advanced registry with plugin metadata"""

    _plugins: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, info: PluginInfo):
        """Decorator with plugin metadata"""
        def decorator(plugin_class):
            cls._plugins[info.name] = {
                'class': plugin_class,
                'info': info,
                'module': plugin_class.__module__
            }
            return plugin_class
        return decorator

    @classmethod
    def get_plugin(cls, name: str):
        """Get plugin class by name"""
        if name not in cls._plugins:
            raise KeyError(f"Plugin '{name}' not found")
        return cls._plugins[name]['class']

    @classmethod
    def get_plugin_info(cls, name: str) -> Optional[PluginInfo]:
        """Get plugin metadata"""
        if name in cls._plugins:
            return cls._plugins[name]['info']
        return None

    @classmethod
    def list_plugins(cls) -> List[str]:
        return list(cls._plugins.keys())

    @classmethod
    def create_plugin(cls, name: str, *args, **kwargs):
        """Create plugin instance"""
        plugin_class = cls.get_plugin(name)
        return plugin_class(*args, **kwargs)

# Usage with metadata


@PluginRegistry.register(PluginInfo(
    name="csv_loader",
    version="1.0.0",
    description="Load data from CSV files",
    author="Data Team"
))
class CSVLoader:
    def load(self, filepath):
        return f"Loading CSV from {filepath}"


@PluginRegistry.register(PluginInfo(
    name="json_loader",
    version="1.2.0",
    description="Load data from JSON files"
))
class JSONLoader:
    def load(self, filepath):
        return f"Loading JSON from {filepath}"


# Test
print(PluginRegistry.list_plugins())  # ['csv_loader', 'json_loader']

loader = PluginRegistry.create_plugin("csv_loader")
print(loader.load("data.csv"))  # Loading CSV from data.csv

info = PluginRegistry.get_plugin_info("csv_loader")
print(f"Author: {info.author}")  # Author: Data Team
