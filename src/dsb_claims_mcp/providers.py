"""Read-only adapters. DSB account access deliberately has no guessed endpoints."""

from __future__ import annotations

import os
from importlib.resources import files
from typing import Protocol

from .models import Dataset


class ProviderError(Exception):
    """Safe, user-readable failure with no raw input or file path."""


class TicketJourneyProvider(Protocol):
    name: str

    def load(self) -> Dataset: ...


class DemoProvider:
    name = "demo"

    def load(self) -> Dataset:
        data = files("dsb_claims_mcp").joinpath("data/demo.json").read_text(encoding="utf-8")
        return Dataset.model_validate_json(data)


class DsbAccountProvider:
    name = "dsb-account"

    def load(self) -> Dataset:
        raise ProviderError(
            "DSB account discovery is not implemented. No approved public account API was "
            "verified. Use demo for development. Do not provide "
            "passwords, cookies, CPR, or session tokens. Authorized access and terms review "
            "are prerequisites for a future adapter."
        )


def configured_provider() -> TicketJourneyProvider:
    mode = os.environ.get("DSB_MCP_PROVIDER", "demo")
    if mode == "demo":
        return DemoProvider()
    if mode == "dsb-account":
        return DsbAccountProvider()
    raise ProviderError("DSB_MCP_PROVIDER must be demo or dsb-account")
