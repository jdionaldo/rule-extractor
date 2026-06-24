"""Tests for Scope validation, containment, and precedence."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from rule_store.hierarchy import Scope, Tier

# --- validation -------------------------------------------------------------


def test_enterprise_scope_needs_no_other_fields() -> None:
    scope = Scope(tier=Tier.ENTERPRISE)
    assert scope.tier is Tier.ENTERPRISE
    assert scope.franchise is None


@pytest.mark.parametrize(
    ("make_scope", "missing_field"),
    [
        (lambda: Scope(tier=Tier.FRANCHISE), "franchise"),
        (lambda: Scope(tier=Tier.BRAND, franchise="Onco"), "brand"),
        (lambda: Scope(tier=Tier.BRAND), "franchise"),
        (
            lambda: Scope(tier=Tier.CHANNEL, franchise="Onco", brand="BrandX"),
            "channel",
        ),
        (
            lambda: Scope(tier=Tier.MARKET, franchise="Onco", brand="BrandX"),
            "market",
        ),
    ],
)
def test_missing_required_field_rejected(
    make_scope: Callable[[], Scope], missing_field: str
) -> None:
    with pytest.raises(ValueError) as exc_info:
        make_scope()
    assert missing_field in str(exc_info.value)


def test_each_tier_constructs_when_required_fields_present(
    enterprise_scope: Scope,
    franchise_scope: Scope,
    brand_scope: Scope,
    channel_scope: Scope,
    market_scope: Scope,
) -> None:
    assert enterprise_scope.tier is Tier.ENTERPRISE
    assert franchise_scope.franchise == "Onco"
    assert brand_scope.brand == "BrandX"
    assert channel_scope.channel == "Meta"
    assert market_scope.market == "DE"


# --- containment ------------------------------------------------------------


def test_enterprise_contains_every_scope(
    enterprise_scope: Scope,
    franchise_scope: Scope,
    brand_scope: Scope,
    channel_scope: Scope,
    market_scope: Scope,
) -> None:
    for scope in (
        enterprise_scope,
        franchise_scope,
        brand_scope,
        channel_scope,
        market_scope,
    ):
        assert enterprise_scope.contains(scope)


def test_franchise_contains_its_descendants_not_enterprise(
    enterprise_scope: Scope,
    franchise_scope: Scope,
    brand_scope: Scope,
    channel_scope: Scope,
    market_scope: Scope,
) -> None:
    assert franchise_scope.contains(franchise_scope)
    assert franchise_scope.contains(brand_scope)
    assert franchise_scope.contains(channel_scope)
    assert franchise_scope.contains(market_scope)
    assert not franchise_scope.contains(enterprise_scope)


def test_brand_contains_channel_and_market_not_franchise(
    franchise_scope: Scope,
    brand_scope: Scope,
    channel_scope: Scope,
    market_scope: Scope,
) -> None:
    assert brand_scope.contains(brand_scope)
    assert brand_scope.contains(channel_scope)
    assert brand_scope.contains(market_scope)
    assert not brand_scope.contains(franchise_scope)


def test_channel_and_market_are_siblings(
    channel_scope: Scope, market_scope: Scope
) -> None:
    assert channel_scope.contains(channel_scope)
    assert market_scope.contains(market_scope)
    assert not channel_scope.contains(market_scope)
    assert not market_scope.contains(channel_scope)


def test_scopes_under_different_brands_do_not_contain() -> None:
    brand_x = Scope(tier=Tier.BRAND, franchise="Onco", brand="BrandX")
    channel_under_y = Scope(
        tier=Tier.CHANNEL, franchise="Onco", brand="BrandY", channel="Meta"
    )
    assert not brand_x.contains(channel_under_y)


def test_market_scopes_under_different_brands_do_not_contain() -> None:
    market_x = Scope(
        tier=Tier.MARKET, franchise="Onco", brand="BrandX", market="DE"
    )
    market_y = Scope(
        tier=Tier.MARKET, franchise="Onco", brand="BrandY", market="DE"
    )
    assert not market_x.contains(market_y)
    assert not market_y.contains(market_x)


# --- precedence -------------------------------------------------------------


def test_outranks_when_higher_tier_and_overlapping(
    enterprise_scope: Scope,
    brand_scope: Scope,
    channel_scope: Scope,
    market_scope: Scope,
) -> None:
    assert enterprise_scope.outranks(market_scope)
    assert brand_scope.outranks(channel_scope)
    assert brand_scope.outranks(market_scope)
    assert not market_scope.outranks(brand_scope)


def test_outranks_is_false_for_equal_scope(brand_scope: Scope) -> None:
    assert not brand_scope.outranks(brand_scope)


def test_outranks_is_false_for_siblings(
    channel_scope: Scope, market_scope: Scope
) -> None:
    assert not channel_scope.outranks(market_scope)
    assert not market_scope.outranks(channel_scope)


def test_outranks_is_false_without_overlap() -> None:
    franchise_onco = Scope(tier=Tier.FRANCHISE, franchise="Onco")
    market_elsewhere = Scope(
        tier=Tier.MARKET, franchise="Immuno", brand="BrandZ", market="DE"
    )
    assert not franchise_onco.outranks(market_elsewhere)
    assert not market_elsewhere.outranks(franchise_onco)
