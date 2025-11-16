
import os
from pathlib import Path
import subprocess
import sys

from core.colors import Colors
from core.decorators import Command, arg
from core.kubectl import KubeCommand
from core.logger import Logger


@Command.register("diff", help="Compare resources", args=[
    arg("resource_type", help="Resource type"),
    arg("resource_name", help="Resource name"),
    arg("filename", help="File to compare"),
])
class DiffCommand:
    """Handle diff subcommand"""

    def __init__(self, kube: KubeCommand):
        self.kube = kube

    def execute(self, args):
        if not all([args.resource_type, args.resource_name, args.filename]):
            Logger.error("RESOURCE_TYPE, RESOURCE_NAME, and FILE are required")
            sys.exit(1)

        filepath = Path(args.filename)
        if not filepath.exists():
            Logger.error(f"File not found: {args.filename}")
            sys.exit(1)

        Logger.info(
            f"Comparing {args.resource_type}/{args.resource_name} with {args.filename}")

        # Get live configuration
        result = self.kube.run([
            "get", args.resource_type, args.resource_name,
            "-n", self.kube.namespace,
            "-o", "yaml"
        ])

        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(result.stdout)
            temp_file = f.name

        try:
            # Run diff
            diff_proc = subprocess.run(
                ["diff", "-u", temp_file, args.filename],
                capture_output=True,
                text=True
            )

            # Color the output
            # Skip first 2 lines
            for line in diff_proc.stdout.splitlines()[2:]:
                if line.startswith('-'):
                    print(f"{Colors.RED}{line}{Colors.RESET}")
                elif line.startswith('+'):
                    print(f"{Colors.GREEN}{line}{Colors.RESET}")
                else:
                    print(line)
        finally:
            os.unlink(temp_file)
