"""Import all command modules to register them with the Command registry"""

from git.commands import (  # noqa: F401
    add,
    backup,
    check,
    clone,
    discover,
    import_github,
    import_gitlab,
    init,
    list_repos,
    push,
    remove,
    status,
    sync,
    validate,
)
