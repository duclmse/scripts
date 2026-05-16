"""Tests for aws.output — render() with all four formats."""
from __future__ import annotations

import json

import yaml

from aws.output import render


def test_json_dict():
    result = render({"key": "value", "num": 42}, fmt="json")
    parsed = json.loads(result)
    assert parsed == {"key": "value", "num": 42}


def test_json_list():
    data = [{"a": 1}, {"a": 2}]
    result = render(data, fmt="json")
    assert json.loads(result) == data


def test_yaml_dict():
    result = render({"x": 1, "y": [2, 3]}, fmt="yaml")
    parsed = yaml.safe_load(result)
    assert parsed["x"] == 1
    assert parsed["y"] == [2, 3]


def test_csv_list_of_dicts():
    data = [{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]
    result = render(data, fmt="csv")
    lines = result.splitlines()
    assert lines[0] == "name,age"
    assert "alice" in lines[1]
    assert "bob" in lines[2]


def test_csv_comma_in_value():
    data = [{"desc": "hello, world"}]
    result = render(data, fmt="csv")
    assert '"hello, world"' in result


def test_table_dict(capsys):
    # Just verify it doesn't raise and returns a non-empty string.
    result = render({"k": "v"}, fmt="table")
    assert "k" in result
    assert "v" in result


def test_table_list_of_dicts():
    data = [{"InstanceId": "i-abc", "State": "running"}]
    result = render(data, fmt="table")
    assert "InstanceId" in result
    assert "i-abc" in result


def test_empty_list():
    result = render([], fmt="table")
    assert isinstance(result, str)


def test_scalar():
    result = render("hello", fmt="json")
    assert json.loads(result) == "hello"


def test_unknown_format_falls_back_to_table():
    result = render({"x": 1}, fmt="unknown")
    # Should fall back without crashing.
    assert isinstance(result, str)
