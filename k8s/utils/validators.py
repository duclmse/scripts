
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
