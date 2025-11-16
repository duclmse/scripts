
import subprocess
import sys
from core.colors import Colors
from core.config import KubeConfig
from core.decorators import Command, arg
from core.logger import Logger


@Command.register("context", aliases=["ctx"], help="Manage contexts", args=[
    arg("context_name", nargs="?", help="Context name"),
    arg("action", choices=["list", "use", "current", "bookmark"],
        help="Action to perform"),
    arg("bookmark_action", nargs="?", choices=["add", "list", "use", "delete"],
        help="Bookmark action"),
    arg("bookmark_name", nargs="?", help="Bookmark name"),
    arg("bookmark_namespace", nargs="?", help="Bookmark namespace"),
])
class ContextCommand:
    """Handle context subcommand"""

    def __init__(self, kube):
        self.kube = kube
        self.config = KubeConfig()

    def execute(self, args):
        """Execute context command"""
        action = args.action

        if action == "list":
            self.list_contexts()
        elif action == "use":
            self.use_context(args.context_name)
        elif action == "current":
            self.show_current()
        elif action == "bookmark":
            self.handle_bookmark(args)
        else:
            Logger.error(f"Unknown action: {action}")
            sys.exit(1)

    def list_contexts(self):
        """List all available contexts"""
        subprocess.run(["kubectl", "config", "get-contexts"])

    def use_context(self, context_name):
        """Switch to a specific context"""
        if not context_name:
            Logger.error("CONTEXT_NAME is required")
            sys.exit(1)

        subprocess.run(["kubectl", "config", "use-context", context_name])
        Logger.success(f"Switched to context: {context_name}")

    def show_current(self):
        """Show current context and namespace"""
        ctx = self.get_current_context()
        print(f"{Colors.BOLD}Current context:{Colors.RESET} {ctx}")
        print(f"{Colors.BOLD}Current namespace:{Colors.RESET} {self.kube.namespace}")

    @staticmethod
    def get_current_context() -> str:
        """Get current kubectl context"""
        try:
            result = subprocess.run(
                ["kubectl", "config", "current-context"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def handle_bookmark(self, args):
        """Handle bookmark subcommands"""
        bookmark_action = args.bookmark_action

        if not bookmark_action:
            # Default to list if no action specified
            self.bookmark_list()
            return

        if bookmark_action == "add":
            self.bookmark_add(args)
        elif bookmark_action == "list":
            self.bookmark_list()
        elif bookmark_action == "use":
            self.bookmark_use(args.bookmark_name)
        elif bookmark_action == "delete":
            self.bookmark_delete(args.bookmark_name)
        else:
            Logger.error(f"Unknown bookmark action: {bookmark_action}")
            sys.exit(1)

    def bookmark_add(self, args):
        """Add a new bookmark"""
        name = args.bookmark_name
        if not name:
            Logger.error("BOOKMARK_NAME is required")
            sys.exit(1)

        ctx = args.context_name if hasattr(
            args, 'context_name') and args.context_name else self.get_current_context()
        ns = args.bookmark_namespace if hasattr(
            args, 'bookmark_namespace') and args.bookmark_namespace else self.kube.namespace

        bookmarks = self.config.get_bookmarks()
        bookmarks[name] = {"context": ctx, "namespace": ns}
        self.config.save_bookmarks(bookmarks)

        Logger.success(
            f"Bookmark '{name}' added (context: {ctx}, namespace: {ns})")

    def bookmark_list(self):
        """List all bookmarks"""
        bookmarks = self.config.get_bookmarks()

        if not bookmarks:
            print("No bookmarks found. Add one with: context bookmark add <name>")
            return

        print(f"{Colors.BOLD}NAME\t\tCONTEXT\t\tNAMESPACE{Colors.RESET}")
        print("-" * 60)
        for name, data in bookmarks.items():
            print(f"{name}\t\t{data['context']}\t\t{data['namespace']}")

    def bookmark_use(self, name):
        """Use a bookmark"""
        if not name:
            Logger.error("BOOKMARK_NAME is required")
            sys.exit(1)

        bookmarks = self.config.get_bookmarks()

        if name not in bookmarks:
            Logger.error(f"Bookmark '{name}' not found")
            available = ', '.join(bookmarks.keys()) if bookmarks else 'none'
            Logger.info(f"Available bookmarks: {available}")
            sys.exit(1)

        data = bookmarks[name]
        subprocess.run(["kubectl", "config", "use-context", data["context"]])
        Logger.success(
            f"Using bookmark '{name}' (context: {data['context']}, namespace: {data['namespace']})")

    def bookmark_delete(self, name):
        """Delete a bookmark"""
        if not name:
            Logger.error("BOOKMARK_NAME is required")
            sys.exit(1)

        bookmarks = self.config.get_bookmarks()

        if name in bookmarks:
            del bookmarks[name]
            self.config.save_bookmarks(bookmarks)
            Logger.success(f"Bookmark '{name}' deleted")
        else:
            Logger.error(f"Bookmark '{name}' not found")
            sys.exit(1)
