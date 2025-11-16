#!/usr/bin/env python3
"""
Git Repository Manager - backward-compatibility shim.
The implementation has moved to the git/ package.

    from git import GitContext, RepoConfig, Statistics
    from git.cli import main, init_parser
    from git.commands.clone import CloneCommand
"""

from git.models import RepoConfig, Statistics  # noqa: F401
from git.context import GitContext             # noqa: F401
from git.cli import init_parser, main          # noqa: F401

if __name__ == '__main__':
    main()
