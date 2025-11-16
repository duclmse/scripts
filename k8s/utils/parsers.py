
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
    
    pattern = r'(\d+)([smhd])'
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
