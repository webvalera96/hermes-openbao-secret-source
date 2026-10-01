"""Unit tests for reference parsing and mapping extraction (tasks 2.2 and 2.3)."""

from __future__ import annotations

import pytest

from agent.secret_sources.base import ErrorKind

from hermes_openbao_secret_source.refs import (
    InvalidReference,
    OpenBaoRef,
    extract_references,
    parse_reference,
)


def test_valid_reference_with_mount_path_and_key():
    ref = parse_reference("openbao://secret/team/llm#api_key")
    assert ref == OpenBaoRef(mount="secret", path="team/llm", key="api_key")


def test_valid_reference_single_segment_path_and_custom_mount():
    ref = parse_reference("openbao://kv-prod/shared#token")
    assert ref == OpenBaoRef(mount="kv-prod", path="shared", key="token")


def test_surrounding_whitespace_is_ignored():
    assert parse_reference("  openbao://secret/team/llm#api_key  ") == OpenBaoRef(
        mount="secret", path="team/llm", key="api_key"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "openbao:///team/llm#api_key",       # mount omitted
        "openbao://secret/team/llm",         # key selector omitted
        "openbao://secret/team/llm#",        # empty key
        "openbao://secret#api_key",          # path omitted
        "openbao://secret/team#llm#api_key", # ambiguous '#'
        "openbao://secret//llm#api_key",     # empty path segment (leading)
        "openbao://secret/team//llm#x",      # empty path segment (middle)
        "openbao://secret/team/#x",          # empty path segment (trailing)
        "vault://secret/team/llm#api_key",   # wrong scheme
        "openbao://",                        # nothing at all
        "",                                  # empty string
        "   ",                               # whitespace only
        None,                                # not a string
        42,                                  # not a string
    ],
)
def test_malformed_references_are_rejected(raw):
    with pytest.raises(InvalidReference):
        parse_reference(raw)


def test_extract_references_mixed_map_yields_valid_entries_and_ref_invalid():
    secrets = {
        "OPENAI_API_KEY": "openbao://secret/team/llm#api_key",
        "ANTHROPIC_API_KEY": "openbao://kv-prod/shared#token",
        "BAD_REF_MISSING_KEY": "openbao://secret/team/llm",
        "BAD_REF_NO_MOUNT": "openbao:///team/llm#api_key",
        "BAD_REF_AMBIGUOUS": "openbao://secret/team#llm#api_key",
    }
    valid, issues = extract_references(secrets)

    assert [name for name, _ in valid] == ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    assert valid[0][1] == OpenBaoRef(mount="secret", path="team/llm", key="api_key")
    assert valid[1][1] == OpenBaoRef(mount="kv-prod", path="shared", key="token")

    assert [issue.env_var for issue in issues] == [
        "BAD_REF_MISSING_KEY",
        "BAD_REF_NO_MOUNT",
        "BAD_REF_AMBIGUOUS",
    ]
    assert all(issue.kind is ErrorKind.REF_INVALID for issue in issues)
    assert all(issue.message for issue in issues)


def test_extract_references_tolerates_non_mapping():
    assert extract_references("not-a-map") == ([], [])
    assert extract_references(None) == ([], [])


def test_extract_references_reports_non_string_env_var_name():
    valid, issues = extract_references({1: "openbao://secret/team/llm#api_key"})
    assert valid == []
    assert len(issues) == 1
    assert issues[0].kind is ErrorKind.REF_INVALID


def test_parsed_reference_round_trips_to_string():
    assert str(parse_reference("openbao://secret/team/llm#api_key")) == "openbao://secret/team/llm#api_key"
