#!/usr/bin/env python3

"""
Kubernetes Manager
"""

import sys
from core.colors import Colors
from core.decorators import Command
from core.logger import Logger

# Import all commands to register them
from .commands import KubeCommand, init_parser, register_commands


def main():
    """Main entry point"""
    parser = init_parser()
    register_commands(parser, Command.get_all_commands())
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Disable colors if requested
    if args.no_color:
        Colors.disable()

    # Create KubeCommand instance
    kube = KubeCommand(
        namespace=args.namespace,
        context=args.context,
        verbose=args.verbose
    )

    # Get command class
    command_class = Command.get_command(args.command)

    if not command_class:
        Logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        command_class(kube).execute(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        Logger.error(f"Command failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
