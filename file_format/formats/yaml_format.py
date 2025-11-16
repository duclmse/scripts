"""YAML format — reads/writes a YAML sequence of mappings"""

from typing import Iterator

from file_format.base import FileFormat, Record

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


if _YAML_AVAILABLE:
    class YAMLFormat(FileFormat, format_name="yaml", file_extensions=(".yaml", ".yml")):
        def __init__(self, encoding: str = "utf-8"):
            self.encoding = encoding

        def read(self, source: str) -> Iterator[Record]:
            with open(source, "r", encoding=self.encoding) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, list):
                raise ValueError(f"Expected a YAML sequence at top level, got {type(data).__name__}")
            yield from data

        def write(self, records: Iterator[Record], destination: str) -> int:
            rows = list(records)
            with open(destination, "w", encoding=self.encoding) as f:
                yaml.dump(rows, f, allow_unicode=True, default_flow_style=False)
            return len(rows)
else:
    class YAMLFormat:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError("pyyaml is required for YAMLFormat: pip install pyyaml")
