"""Conformance checks via the Hermes ``SecretSourceConformance`` kit (task 5.1)."""

from __future__ import annotations

import pytest

from tests.secret_sources.conformance import SecretSourceConformance

from hermes_openbao_secret_source.source import OpenBaoSource


class TestOpenBaoSourceConformance(SecretSourceConformance):
    @pytest.fixture
    def source(self):
        return OpenBaoSource()
