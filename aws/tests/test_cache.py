"""Tests for aws.cache."""
from __future__ import annotations

import time

import pytest

from aws.cache import Cache
from aws.exceptions import CacheError


@pytest.fixture
def cache(tmp_path):
    return Cache(cache_dir=str(tmp_path), default_ttl=300)


def test_set_and_get(cache):
    cache.set("hello", {"value": 42})
    assert cache.get("hello") == {"value": 42}


def test_miss_returns_none(cache):
    assert cache.get("nonexistent") is None


def test_ttl_expiry(tmp_path):
    c = Cache(cache_dir=str(tmp_path), default_ttl=1)
    c.set("expiring", "data", ttl=1)
    assert c.get("expiring") == "data"
    # Manually expire by poking the underlying file
    import pickle, os
    for f in tmp_path.glob("*.pkl"):
        with f.open("rb") as fh:
            entry = pickle.load(fh)
        entry["exp"] = time.monotonic() - 1  # already expired
        with f.open("wb") as fh:
            pickle.dump(entry, fh)
    assert c.get("expiring") is None


def test_no_expiry_when_ttl_zero(tmp_path):
    c = Cache(cache_dir=str(tmp_path), default_ttl=0)
    c.set("forever", "stays", ttl=0)
    assert c.get("forever") == "stays"


def test_delete(cache):
    cache.set("removeme", 99)
    assert cache.delete("removeme") is True
    assert cache.get("removeme") is None
    assert cache.delete("removeme") is False  # already gone


def test_clear_all(cache):
    cache.set("a", 1)
    cache.set("b", 2)
    deleted = cache.clear()
    assert deleted == 2
    assert cache.get("a") is None


def test_clear_prefix(cache):
    cache.set("ec2:instances", [1, 2])
    cache.set("s3:buckets", ["my-bucket"])
    deleted = cache.clear(prefix="ec2:")
    assert deleted == 1
    assert cache.get("ec2:instances") is None
    assert cache.get("s3:buckets") == ["my-bucket"]


def test_stats(cache):
    cache.set("x", 1)
    cache.set("y", 2)
    stats = cache.stats()
    assert stats["total"] == 2
    assert stats["valid"] == 2
    assert stats["expired"] == 0


def test_atomic_write_no_partial_read(tmp_path):
    """Concurrent-safe: a .tmp file should never be returned as a cache hit."""
    c = Cache(cache_dir=str(tmp_path))
    c.set("key", "value")
    # No .tmp files should remain.
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert not tmp_files


def test_corrupted_file_returns_none(tmp_path):
    c = Cache(cache_dir=str(tmp_path))
    c.set("corrupt", "ok")
    # Overwrite with garbage.
    for f in tmp_path.glob("*.pkl"):
        f.write_bytes(b"not pickle data")
    assert c.get("corrupt") is None
