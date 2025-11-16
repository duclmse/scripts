
"""Favorite commands manager"""
from core.decorators import Command, arg
from core.logger import Logger
from core.config import KubeConfig


@Command.register("fav", help="Manage favorite commands", args=[
    arg("action", choices=["add", "list", "run", "delete"], help="Action"),
    arg("name", nargs="?", help="Favorite name"),
    arg("command", nargs="*", help="Command to save"),
])
class FavCommand:
    """Save and run frequent commands"""

    def __init__(self, kube):
        self.kube = kube
        self.config = KubeConfig()

    def execute(self, args):
        match args.action:
            case"add":
                self.add_favorite(args)
            case "list":
                self.list_favorites()
            case "run":
                self.run_favorite(args.name)
            case "delete":
                self.delete_favorite(args.name)

    def add_favorite(self, args):
        """Add a new favorite"""
        if not args.name or not args.command:
            Logger.error("Name and command required")
            return

        favorites = self.config.get_favorites()
        favorites[args.name] = {
            "command": " ".join(args.command),
            "namespace": self.kube.namespace,
            "context": self.kube.get_current_context()
        }
        self.config.save_favorites(favorites)
        Logger.success(f"Saved favorite: {args.name}")

    def list_favorites(self):
        """List all favorites"""
        favorites = self.config.get_favorites()

        if not favorites:
            print("No favorites saved")
            return

        print(f"{'NAME':<20} {'COMMAND':<50}")
        print("-" * 70)
        for name, data in favorites.items():
            print(f"{name:<20} {data['command']:<50}")

    def run_favorite(self, name):
        """Run a saved favorite"""
        if not name:
            Logger.error("Favorite name required")
            return

        favorites = self.config.get_favorites()

        if name not in favorites:
            Logger.error(f"Favorite '{name}' not found")
            return

        fav = favorites[name]
        Logger.info(f"Running: {fav['command']}")

        import subprocess
        subprocess.run(fav['command'], shell=True)

    def delete_favorite(self, name):
        """Delete a favorite"""
        if not name:
            Logger.error("Favorite name required")
            return

        favorites = self.config.get_favorites()

        if name in favorites:
            del favorites[name]
            self.config.save_favorites(favorites)
            Logger.success(f"Deleted favorite: {name}")
        else:
            Logger.error(f"Favorite '{name}' not found")
