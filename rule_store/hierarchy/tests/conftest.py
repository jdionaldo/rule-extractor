"""Shared pytest fixtures: one example Scope per tier.

The fixtures share a single ancestor path (franchise "Onco", brand "BrandX") so
that the broader scopes genuinely contain the narrower ones.
"""

from __future__ import annotations

import pytest

from rule_store.hierarchy import Scope, Tier


@pytest.fixture
def enterprise_scope() -> Scope:
    """An ENTERPRISE scope (no discriminators)."""
    return Scope(tier=Tier.ENTERPRISE)


@pytest.fixture
def franchise_scope() -> Scope:
    """A FRANCHISE scope under franchise 'Onco'."""
    return Scope(tier=Tier.FRANCHISE, franchise="Onco")


@pytest.fixture
def brand_scope() -> Scope:
    """A BRAND scope for 'BrandX' under franchise 'Onco'."""
    return Scope(tier=Tier.BRAND, franchise="Onco", brand="BrandX")


@pytest.fixture
def channel_scope() -> Scope:
    """A CHANNEL scope for 'Meta' under Onco/BrandX."""
    return Scope(
        tier=Tier.CHANNEL, franchise="Onco", brand="BrandX", channel="Meta"
    )


@pytest.fixture
def market_scope() -> Scope:
    """A MARKET scope for 'DE' under Onco/BrandX."""
    return Scope(
        tier=Tier.MARKET, franchise="Onco", brand="BrandX", market="DE"
    )
