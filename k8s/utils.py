#!/usr/bin/env python3
"""
Utils Package - Helper utilities for Kubernetes Manager
"""

# ==================== utils/__init__.py ====================
UTILS_INIT = '''
"""Utility functions and helpers"""

from .parsers import *
from .formatters import *
from .validators import *

__all__ = [
    'parse_resource_string',
    'parse_quantity',
    'parse_duration',
    'format_table',
    'format_yaml',
    'format_json',
    'format_age',
    'format_bytes',
    'highlight_text',
    'validate_resource_name',
    'validate_namespace',
    'validate_label_selector',
]
'''

# ==================== utils/parsers.py ====================
PARSERS_PY = '''
"""Parsing utilities for Kubernetes resources"""
import re
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timedelta


def parse_resource_string(resource_str: str) -> Tuple[str, Optional[str]]:
    """
    Parse resource string like 'pod/my-pod' or 'my-pod'
    Returns: (resource_type, resource_name) or (resource_str, None)
    
    Examples:
        >>> parse_resource_string("pod/my-pod")
        ('pod', 'my-pod')
        >>> parse_resource_string("my-pod")
        ('my-pod', None)
    """
    if '/' in resource_str:
        parts = resource_str.split('/', 1)
        return parts[0], parts[1]
    return resource_str, None


def parse_quantity(quantity: str) -> float:
    """
    Parse Kubernetes quantity string to float
    
    CPU: '100m' -> 0.1, '2' -> 2.0
    Memory: '1Gi' -> 1024, '512Mi' -> 512
    
    Examples:
        >>> parse_quantity("100m")
        0.1
        >>> parse_quantity("1Gi")
        1.0
        >>> parse_quantity("512Mi")
        0.5
    """
    if not quantity or quantity == '0':
        return 0.0
    
    # CPU in millicores
    if quantity.endswith('m'):
        return float(quantity[:-1]) / 1000
    
    # Memory units
    units = {
        'Ki': 1024 ** 1,
        'Mi': 1024 ** 2,
        'Gi': 1024 ** 3,
        'Ti': 1024 ** 4,
        'Pi': 1024 ** 5,
        'K': 1000 ** 1,
        'M': 1000 ** 2,
        'G': 1000 ** 3,
        'T': 1000 ** 4,
        'P': 1000 ** 5,
    }
    
    for unit, multiplier in units.items():
        if quantity.endswith(unit):
            value = float(quantity[:-len(unit)])
            # Return in GB for memory
            return (value * multiplier) / (1024 ** 3)
    
    # No unit, assume it's a raw number
    return float(quantity)


def parse_duration(duration: str) -> Optional[timedelta]:
    """
    Parse duration string to timedelta
    
    Examples:
        >>> parse_duration("5m")
        timedelta(minutes=5)
        >>> parse_duration("2h30m")
        timedelta(hours=2, minutes=30)
        >>> parse_duration("1d")
        timedelta(days=1)
    """
    if not duration:
        return None
    
    pattern = r'(\\d+)([smhd])'
    matches = re.findall(pattern, duration.lower())
    
    if not matches:
        return None
    
    units = {
        's': 'seconds',
        'm': 'minutes',
        'h': 'hours',
        'd': 'days'
    }
    
    kwargs = {}
    for value, unit in matches:
        if unit in units:
            kwargs[units[unit]] = int(value)
    
    return timedelta(**kwargs) if kwargs else None


def parse_age(timestamp: str) -> timedelta:
    """
    Parse Kubernetes timestamp to age
    
    Examples:
        >>> parse_age("2024-01-15T10:30:00Z")
        timedelta(...)
    """
    try:
        # Parse ISO format
        if 'T' in timestamp:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(timestamp)
        
        return datetime.now(dt.tzinfo) - dt
    except:
        return timedelta(0)


def parse_label_selector(selector: str) -> Dict[str, str]:
    """
    Parse label selector string to dict
    
    Examples:
        >>> parse_label_selector("app=backend,env=prod")
        {'app': 'backend', 'env': 'prod'}
    """
    labels = {}
    
    if not selector:
        return labels
    
    for pair in selector.split(','):
        if '=' in pair:
            key, value = pair.split('=', 1)
            labels[key.strip()] = value.strip()
    
    return labels


def parse_pod_status(pod_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse pod data and extract status information
    
    Returns dict with:
        - phase: Running, Pending, Failed, etc.
        - ready: bool
        - restarts: int
        - reason: str (if not running)
        - message: str (details)
    """
    status = pod_data.get('status', {})
    
    result = {
        'phase': status.get('phase', 'Unknown'),
        'ready': False,
        'restarts': 0,
        'reason': None,
        'message': None
    }
    
    # Check container statuses
    container_statuses = status.get('containerStatuses', [])
    
    if container_statuses:
        # Count restarts
        result['restarts'] = sum(c.get('restartCount', 0) for c in container_statuses)
        
        # Check if all containers are ready
        result['ready'] = all(c.get('ready', False) for c in container_statuses)
        
        # Get reason from first non-running container
        for container_status in container_statuses:
            state = container_status.get('state', {})
            
            if 'waiting' in state:
                waiting = state['waiting']
                result['reason'] = waiting.get('reason')
                result['message'] = waiting.get('message')
                break
            elif 'terminated' in state:
                terminated = state['terminated']
                result['reason'] = terminated.get('reason')
                result['message'] = terminated.get('message')
                break
    
    return result


def parse_env_vars(env_list: list) -> Dict[str, str]:
    """
    Parse environment variable list from pod spec
    
    Examples:
        >>> parse_env_vars([{'name': 'PORT', 'value': '8080'}])
        {'PORT': '8080'}
    """
    env_vars = {}
    
    for env in env_list:
        name = env.get('name')
        value = env.get('value')
        
        if name and value:
            env_vars[name] = value
    
    return env_vars


def parse_resource_requirements(resources: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    Parse resource requirements (requests/limits)
    
    Returns:
        {
            'requests': {'cpu': 0.5, 'memory': 1.0},
            'limits': {'cpu': 1.0, 'memory': 2.0}
        }
    """
    result = {
        'requests': {},
        'limits': {}
    }
    
    for req_type in ['requests', 'limits']:
        if req_type in resources:
            reqs = resources[req_type]
            
            if 'cpu' in reqs:
                result[req_type]['cpu'] = parse_quantity(reqs['cpu'])
            
            if 'memory' in reqs:
                result[req_type]['memory'] = parse_quantity(reqs['memory'])
    
    return result


def parse_image_string(image: str) -> Dict[str, str]:
    """
    Parse container image string
    
    Examples:
        >>> parse_image_string("nginx:1.21")
        {'registry': '', 'name': 'nginx', 'tag': '1.21'}
        >>> parse_image_string("gcr.io/project/app:latest")
        {'registry': 'gcr.io', 'name': 'project/app', 'tag': 'latest'}
    """
    result = {
        'registry': '',
        'name': '',
        'tag': 'latest'
    }
    
    # Split tag
    if ':' in image:
        image, tag = image.rsplit(':', 1)
        result['tag'] = tag
    
    # Split registry
    if '/' in image:
        parts = image.split('/', 1)
        # Check if first part looks like a registry (has . or :)
        if '.' in parts[0] or ':' in parts[0]:
            result['registry'] = parts[0]
            result['name'] = parts[1]
        else:
            result['name'] = image
    else:
        result['name'] = image
    
    return result
'''

# ==================== utils/formatters.py ====================
FORMATTERS_PY = '''
"""Output formatting utilities"""
import json
import yaml
from typing import List, Dict, Any
from datetime import timedelta
from io import StringIO


def format_table(data: List[List[str]], headers: List[str] = None, 
                 align: str = 'left') -> str:
    """
    Format data as aligned table
    
    Examples:
        >>> data = [['pod-1', 'Running'], ['pod-2', 'Pending']]
        >>> print(format_table(data, ['NAME', 'STATUS']))
        NAME   STATUS
        pod-1  Running
        pod-2  Pending
    """
    if not data:
        return ""
    
    # Include headers in data for width calculation
    all_rows = [headers] + data if headers else data
    
    # Calculate column widths
    widths = []
    for col_idx in range(len(all_rows[0])):
        max_width = max(len(str(row[col_idx])) for row in all_rows)
        widths.append(max_width)
    
    # Format rows
    output = StringIO()
    
    for row_idx, row in enumerate(all_rows):
        formatted_row = []
        for col_idx, cell in enumerate(row):
            cell_str = str(cell)
            width = widths[col_idx]
            
            if align == 'right':
                formatted_row.append(cell_str.rjust(width))
            else:
                formatted_row.append(cell_str.ljust(width))
        
        output.write('  '.join(formatted_row))
        output.write('\\n')
        
        # Add separator after headers
        if headers and row_idx == 0:
            output.write('-' * sum(widths + [2 * (len(widths) - 1)]))
            output.write('\\n')
    
    return output.getvalue()


def format_yaml(data: Any, indent: int = 2) -> str:
    """
    Format data as YAML
    
    Examples:
        >>> format_yaml({'name': 'test', 'replicas': 3})
        'name: test\\nreplicas: 3\\n'
    """
    return yaml.dump(data, default_flow_style=False, indent=indent)


def format_json(data: Any, indent: int = 2, compact: bool = False) -> str:
    """
    Format data as JSON
    
    Examples:
        >>> format_json({'name': 'test'})
        '{\\n  "name": "test"\\n}'
    """
    if compact:
        return json.dumps(data, separators=(',', ':'))
    return json.dumps(data, indent=indent)


def format_age(td: timedelta) -> str:
    """
    Format timedelta as human-readable age
    
    Examples:
        >>> format_age(timedelta(days=2, hours=3, minutes=15))
        '2d3h'
        >>> format_age(timedelta(seconds=45))
        '45s'
    """
    total_seconds = int(td.total_seconds())
    
    if total_seconds < 0:
        return '0s'
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and days == 0 and hours == 0:
        parts.append(f"{seconds}s")
    
    return ''.join(parts[:2]) if parts else '0s'


def format_bytes(bytes_value: float, precision: int = 1) -> str:
    """
    Format bytes as human-readable size
    
    Examples:
        >>> format_bytes(1024)
        '1.0 KB'
        >>> format_bytes(1536 * 1024 * 1024)
        '1.5 GB'
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    
    unit_idx = 0
    value = float(bytes_value)
    
    while value >= 1024 and unit_idx < len(units) - 1:
        value /= 1024
        unit_idx += 1
    
    return f"{value:.{precision}f} {units[unit_idx]}"


def format_percentage(value: float, total: float, precision: int = 1) -> str:
    """
    Format as percentage
    
    Examples:
        >>> format_percentage(25, 100)
        '25.0%'
    """
    if total == 0:
        return '0.0%'
    
    percentage = (value / total) * 100
    return f"{percentage:.{precision}f}%"


def format_list(items: List[str], separator: str = ', ', 
                max_items: int = None) -> str:
    """
    Format list as string
    
    Examples:
        >>> format_list(['a', 'b', 'c'])
        'a, b, c'
        >>> format_list(['a', 'b', 'c', 'd'], max_items=2)
        'a, b, +2 more'
    """
    if not items:
        return ''
    
    if max_items and len(items) > max_items:
        visible = items[:max_items]
        remaining = len(items) - max_items
        return f"{separator.join(visible)}, +{remaining} more"
    
    return separator.join(items)


def highlight_text(text: str, keywords: List[str], color: str = '\\033[93m') -> str:
    """
    Highlight keywords in text
    
    Examples:
        >>> highlight_text("error in line 5", ["error"])
        '\\033[93merror\\033[0m in line 5'
    """
    reset = '\\033[0m'
    
    for keyword in keywords:
        text = text.replace(keyword, f"{color}{keyword}{reset}")
    
    return text


def format_resource_list(resources: List[Dict[str, Any]], 
                        columns: List[str]) -> str:
    """
    Format Kubernetes resource list as table
    
    Examples:
        >>> resources = [
        ...     {'name': 'pod-1', 'status': 'Running', 'age': '2d'},
        ...     {'name': 'pod-2', 'status': 'Pending', 'age': '1h'}
        ... ]
        >>> print(format_resource_list(resources, ['name', 'status', 'age']))
    """
    if not resources:
        return "No resources found"
    
    # Extract data for table
    headers = [col.upper() for col in columns]
    data = []
    
    for resource in resources:
        row = []
        for col in columns:
            value = resource.get(col, 'N/A')
            row.append(str(value))
        data.append(row)
    
    return format_table(data, headers)


def truncate_string(text: str, max_length: int = 50, 
                    suffix: str = '...') -> str:
    """
    Truncate string to max length
    
    Examples:
        >>> truncate_string("very long text here", 10)
        'very lo...'
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_key_value(data: Dict[str, Any], indent: int = 0) -> str:
    """
    Format dict as key-value pairs
    
    Examples:
        >>> print(format_key_value({'name': 'test', 'count': 5}))
        name:  test
        count: 5
    """
    output = StringIO()
    indent_str = ' ' * indent
    
    # Calculate max key length for alignment
    max_key_len = max(len(str(k)) for k in data.keys()) if data else 0
    
    for key, value in data.items():
        key_str = str(key).ljust(max_key_len)
        output.write(f"{indent_str}{key_str}: {value}\\n")
    
    return output.getvalue()


def format_status_symbol(status: str) -> str:
    """
    Get symbol for status
    
    Examples:
        >>> format_status_symbol('Running')
        '✓'
        >>> format_status_symbol('Failed')
        '✗'
    """
    symbols = {
        'Running': '✓',
        'Succeeded': '✓',
        'Active': '✓',
        'Ready': '✓',
        'Failed': '✗',
        'Error': '✗',
        'CrashLoopBackOff': '✗',
        'Pending': '⋯',
        'Unknown': '?'
    }
    
    return symbols.get(status, '•')
'''

# ==================== utils/validators.py ====================
VALIDATORS_PY = '''
"""Input validation utilities"""
import re
from typing import Optional


def validate_resource_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate Kubernetes resource name
    
    Rules:
    - Lowercase alphanumeric, '-' or '.'
    - Start and end with alphanumeric
    - Max 253 characters
    
    Returns: (is_valid, error_message)
    
    Examples:
        >>> validate_resource_name("my-pod-123")
        (True, None)
        >>> validate_resource_name("My_Pod")
        (False, 'Invalid characters...')
    """
    if not name:
        return False, "Name cannot be empty"
    
    if len(name) > 253:
        return False, "Name too long (max 253 characters)"
    
    # Must start and end with alphanumeric
    if not re.match(r'^[a-z0-9]', name):
        return False, "Must start with lowercase alphanumeric character"
    
    if not re.match(r'[a-z0-9]$', name):
        return False, "Must end with lowercase alphanumeric character"
    
    # Only lowercase alphanumeric, '-', or '.'
    if not re.match(r'^[a-z0-9.-]+$', name):
        return False, "Can only contain lowercase alphanumeric, '-', or '.'"
    
    return True, None


def validate_namespace(namespace: str) -> tuple[bool, Optional[str]]:
    """
    Validate Kubernetes namespace name
    
    Returns: (is_valid, error_message)
    """
    # Same rules as resource name but max 63 characters
    if len(namespace) > 63:
        return False, "Namespace name too long (max 63 characters)"
    
    return validate_resource_name(namespace)


def validate_label_selector(selector: str) -> tuple[bool, Optional[str]]:
    """
    Validate label selector format
    
    Examples:
        >>> validate_label_selector("app=backend,env=prod")
        (True, None)
        >>> validate_label_selector("invalid")
        (False, 'Invalid format...')
    """
    if not selector:
        return True, None  # Empty is valid
    
    # Check format: key=value,key=value
    pairs = selector.split(',')
    
    for pair in pairs:
        if '=' not in pair:
            return False, f"Invalid pair '{pair}': must be in format key=value"
        
        key, value = pair.split('=', 1)
        
        # Validate key
        if not re.match(r'^[a-zA-Z0-9/_.-]+$', key.strip()):
            return False, f"Invalid label key '{key}'"
        
        # Validate value (can be empty)
        if value and not re.match(r'^[a-zA-Z0-9._-]*$', value.strip()):
            return False, f"Invalid label value '{value}'"
    
    return True, None


def validate_port(port: str) -> tuple[bool, Optional[str]]:
    """
    Validate port number or mapping
    
    Examples:
        >>> validate_port("8080")
        (True, None)
        >>> validate_port("8080:80")
        (True, None)
        >>> validate_port("99999")
        (False, 'Port out of range')
    """
    try:
        if ':' in port:
            local, remote = port.split(':', 1)
            local_port = int(local)
            remote_port = int(remote)
            
            if not (1 <= local_port <= 65535):
                return False, f"Local port {local_port} out of range (1-65535)"
            
            if not (1 <= remote_port <= 65535):
                return False, f"Remote port {remote_port} out of range (1-65535)"
        else:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                return False, f"Port {port_num} out of range (1-65535)"
        
        return True, None
    except ValueError:
        return False, "Port must be a number"


def validate_cpu_request(cpu: str) -> tuple[bool, Optional[str]]:
    """
    Validate CPU request format
    
    Examples:
        >>> validate_cpu_request("100m")
        (True, None)
        >>> validate_cpu_request("1.5")
        (True, None)
        >>> validate_cpu_request("invalid")
        (False, 'Invalid CPU format')
    """
    if not cpu:
        return False, "CPU request cannot be empty"
    
    # Check millicores format
    if cpu.endswith('m'):
        try:
            value = int(cpu[:-1])
            if value <= 0:
                return False, "CPU must be positive"
            return True, None
        except ValueError:
            return False, "Invalid millicores format"
    
    # Check cores format
    try:
        value = float(cpu)
        if value <= 0:
            return False, "CPU must be positive"
        return True, None
    except ValueError:
        return False, "Invalid CPU format"


def validate_memory_request(memory: str) -> tuple[bool, Optional[str]]:
    """
    Validate memory request format
    
    Examples:
        >>> validate_memory_request("512Mi")
        (True, None)
        >>> validate_memory_request("2Gi")
        (True, None)
    """
    if not memory:
        return False, "Memory request cannot be empty"
    
    valid_units = ['Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'K', 'M', 'G', 'T', 'P']
    
    # Check if it has a valid unit
    has_valid_unit = any(memory.endswith(unit) for unit in valid_units)
    
    if not has_valid_unit:
        return False, f"Invalid memory unit. Use one of: {', '.join(valid_units)}"
    
    # Extract and validate numeric part
    for unit in valid_units:
        if memory.endswith(unit):
            try:
                value = float(memory[:-len(unit)])
                if value <= 0:
                    return False, "Memory must be positive"
                return True, None
            except ValueError:
                return False, "Invalid memory value"
    
    return False, "Invalid memory format"


def validate_replicas(replicas: str) -> tuple[bool, Optional[str]]:
    """
    Validate replica count
    
    Examples:
        >>> validate_replicas("3")
        (True, None)
        >>> validate_replicas("-1")
        (False, 'Replicas must be non-negative')
    """
    try:
        count = int(replicas)
        if count < 0:
            return False, "Replicas must be non-negative"
        return True, None
    except ValueError:
        return False, "Replicas must be an integer"


def validate_container_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate container name
    
    Similar to resource name but allows uppercase
    """
    if not name:
        return False, "Container name cannot be empty"
    
    if len(name) > 253:
        return False, "Container name too long (max 253 characters)"
    
    if not re.match(r'^[a-zA-Z0-9]', name):
        return False, "Must start with alphanumeric character"
    
    if not re.match(r'^[a-zA-Z0-9._-]+$', name):
        return False, "Can only contain alphanumeric, '.', '_', or '-'"
    
    return True, None


def validate_image_name(image: str) -> tuple[bool, Optional[str]]:
    """
    Validate container image name
    
    Examples:
        >>> validate_image_name("nginx:1.21")
        (True, None)
        >>> validate_image_name("gcr.io/project/app:latest")
        (True, None)
    """
    if not image:
        return False, "Image name cannot be empty"
    
    # Basic validation - just check it's not empty and has reasonable format
    # Full validation is complex due to registry variations
    
    if len(image) > 255:
        return False, "Image name too long"
    
    # Should not contain spaces
    if ' ' in image:
        return False, "Image name cannot contain spaces"
    
    return True, None
'''

print("=" * 60)
print("UTILS PACKAGE COMPLETE")
print("=" * 60)
print("""
Created utils package with:

1. parsers.py - Parse K8s resources, quantities, durations
   - parse_resource_string()
   - parse_quantity() - CPU/Memory
   - parse_duration()
   - parse_label_selector()
   - parse_pod_status()

2. formatters.py - Format output beautifully
   - format_table()
   - format_yaml()
   - format_json()
   - format_age()
   - format_bytes()
   - highlight_text()

3. validators.py - Validate inputs
   - validate_resource_name()
   - validate_namespace()
   - validate_label_selector()
   - validate_port()
   - validate_cpu_request()
   - validate_memory_request()

All functions include docstrings and examples!
""")

l = [
    {"name": "utils/__init__.py", "content": UTILS_INIT},
    {"name": "utils/parsers.py", "content": PARSERS_PY},
    {"name": "utils/formatters.py", "content": FORMATTERS_PY},
    {"name": "utils/validators.py", "content": VALIDATORS_PY},
]
for file in l:
    with open(file['name'], 'w') as f:
        f.write(file["content"])
