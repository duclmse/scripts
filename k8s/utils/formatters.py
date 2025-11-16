
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
        output.write('\n')
        
        # Add separator after headers
        if headers and row_idx == 0:
            output.write('-' * sum(widths + [2 * (len(widths) - 1)]))
            output.write('\n')
    
    return output.getvalue()


def format_yaml(data: Any, indent: int = 2) -> str:
    """
    Format data as YAML
    
    Examples:
        >>> format_yaml({'name': 'test', 'replicas': 3})
        'name: test\nreplicas: 3\n'
    """
    return yaml.dump(data, default_flow_style=False, indent=indent)


def format_json(data: Any, indent: int = 2, compact: bool = False) -> str:
    """
    Format data as JSON
    
    Examples:
        >>> format_json({'name': 'test'})
        '{\n  "name": "test"\n}'
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


def highlight_text(text: str, keywords: List[str], color: str = '\033[93m') -> str:
    """
    Highlight keywords in text
    
    Examples:
        >>> highlight_text("error in line 5", ["error"])
        '\033[93merror\033[0m in line 5'
    """
    reset = '\033[0m'
    
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
        output.write(f"{indent_str}{key_str}: {value}\n")
    
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
