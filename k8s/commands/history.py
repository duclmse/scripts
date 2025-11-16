
"""Resource change history tracking"""
import json
from datetime import datetime
from pathlib import Path
from core.decorators import Command, arg
from core.logger import Logger
from core.config import HISTORY_DIR

@Command.register("history", help="Show resource change history", args=[
    arg("action", choices=["save", "list", "diff", "restore"], help="Action"),
    arg("resource_type", nargs="?", help="Resource type"),
    arg("resource_name", nargs="?", help="Resource name"),
    arg("--snapshot-id", help="Snapshot ID for restore/diff"),
])
class HistoryCommand:
    """Track resource changes over time"""
    
    def __init__(self, kube):
        self.kube = kube
    
    def execute(self, args):
        if args.action == "save":
            self.save_snapshot(args)
        elif args.action == "list":
            self.list_snapshots(args)
        elif args.action == "diff":
            self.show_diff(args)
        elif args.action == "restore":
            self.restore_snapshot(args)
    
    def save_snapshot(self, args):
        """Save current state"""
        if not args.resource_type or not args.resource_name:
            Logger.error("Resource type and name required")
            return
        
        result = self.kube.run([
            "get", args.resource_type, args.resource_name,
            "-n", self.kube.namespace, "-o", "yaml"
        ])
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{args.resource_type}_{args.resource_name}_{timestamp}.yaml"
        filepath = HISTORY_DIR / filename
        
        filepath.write_text(result.stdout)
        Logger.success(f"Snapshot saved: {filename}")
    
    def list_snapshots(self, args):
        """List available snapshots"""
        snapshots = sorted(HISTORY_DIR.glob("*.yaml"), reverse=True)
        
        if not snapshots:
            print("No snapshots found")
            return
        
        print(f"{'ID':<5} {'TYPE':<15} {'NAME':<30} {'DATE':<20}")
        print("-" * 70)
        
        for i, snap in enumerate(snapshots[:20], 1):
            parts = snap.stem.split("_")
            rtype = parts[0]
            rname = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]
            date = f"{parts[-2]}_{parts[-1]}"
            print(f"{i:<5} {rtype:<15} {rname:<30} {date:<20}")
    
    def show_diff(self, args):
        """Show diff between current and snapshot"""
        Logger.info("Diff functionality - comparing states...")
        # Implementation: Use difflib to compare YAML
    
    def restore_snapshot(self, args):
        """Restore from snapshot"""
        Logger.info("Restore functionality...")
        # Implementation: kubectl apply from snapshot file
