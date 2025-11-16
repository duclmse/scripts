"""FileFormat ABC and FormatRegistry for auto-registration of format classes"""

import abc
from typing import Any, Iterator

Record = dict[str, Any]


class FormatRegistry:
    """
    Mixin that auto-registers subclasses by format_name and file extensions.
    Registration happens at class-definition time via __init_subclass__.
    """

    _registry: dict[str, type] = {}
    _ext_map: dict[str, type] = {}

    def __init_subclass__(
        cls,
        format_name: str | None = None,
        file_extensions: tuple[str, ...] = (),
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        if format_name:
            cls.format_name = format_name
            cls.file_extensions = file_extensions
            FormatRegistry._registry[format_name] = cls
            for ext in file_extensions:
                FormatRegistry._ext_map[ext.lower()] = cls

    @classmethod
    def get(cls, name: str) -> type | None:
        return cls._registry.get(name.lower())

    @classmethod
    def get_by_extension(cls, ext: str) -> type | None:
        return cls._ext_map.get(ext.lower())

    @classmethod
    def list_formats(cls) -> list[str]:
        return sorted(cls._registry.keys())


class FileFormat(abc.ABC, FormatRegistry):
    """
    Abstract base for all file formats.

    Subclasses declare their format name and extensions as class keyword args:

        class CSVFormat(FileFormat, format_name="csv", file_extensions=(".csv",)):
            ...

    This auto-registers the class in FormatRegistry at import time.
    """

    format_name: str | None = None
    file_extensions: tuple[str, ...] = ()

    @abc.abstractmethod
    def read(self, source: str) -> Iterator[Record]:
        """Yield one Record (dict) at a time from source path. Should be a generator."""
        ...

    @abc.abstractmethod
    def write(self, records: Iterator[Record], destination: str) -> int:
        """Write records to destination. Returns count of records written."""
        ...

    def describe(self) -> str:
        return f"{self.__class__.__name__}(format={self.format_name})"
