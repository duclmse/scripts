"""Import all command modules to register them"""

from . import apply
from . import backup
from . import bulk
from . import clone
from . import compare
from . import complete
from . import context
from . import cost
from . import debug
from . import delete
from . import deps
from . import describe
from . import diff
from . import doctor
from . import events
from . import exec
from . import fav
from . import get
from . import git_deploy
from . import health
from . import history
from . import interactive
from . import jobs
from . import list
from . import logs
from . import logs_merge
from . import net_debug
from . import port_forward
from . import ports
from . import restart
from . import rollout
from . import scale
from . import secrets
from . import shell_all
from . import size
from . import snippet
from . import status
from . import template
from . import top
from . import tree
from . import validate
from . import watch
from . import watch_alert

__all__ = [
    'apply',
    'backup',
    'bulk',
    'clone',
    'compare',
    'complete',
    'context',
    'cost',
    'debug',
    'delete',
    'deps',
    'describe',
    'diff',
    'doctor',
    'events',
    'exec',
    'fav',
    'get',
    'git_deploy',
    'health',
    'history',
    'interactive',
    'jobs',
    'list',
    'logs_merge',
    'logs',
    'net_debug',
    'port_forward',
    'ports',
    'restart',
    'rollout',
    'scale',
    'secrets',
    'shell_all',
    'size',
    'snippet',
    'status',
    'template',
    'top',
    'tree',
    'validate',
    'watch_alert',
    'watch',
]


def something():
    print("something")
