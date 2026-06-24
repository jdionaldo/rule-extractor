"""Tests for tier precedence and the owner-role registry."""

from __future__ import annotations

import pytest

from rule_store.hierarchy import OwnerRole, Tier, owner_role_for


def test_precedence_order_highest_to_lowest() -> None:
    assert (
        Tier.ENTERPRISE
        > Tier.FRANCHISE
        > Tier.BRAND
        > Tier.CHANNEL
        > Tier.MARKET
    )


def test_precedence_is_total_and_sorts_low_to_high() -> None:
    assert sorted(Tier) == [
        Tier.MARKET,
        Tier.CHANNEL,
        Tier.BRAND,
        Tier.FRANCHISE,
        Tier.ENTERPRISE,
    ]


def test_enterprise_is_the_highest_authority() -> None:
    assert max(Tier) is Tier.ENTERPRISE


@pytest.mark.parametrize(
    ("tier", "role"),
    [
        (Tier.ENTERPRISE, OwnerRole.ENTERPRISE_LEAD),
        (Tier.FRANCHISE, OwnerRole.FRANCHISE_LEAD),
        (Tier.BRAND, OwnerRole.BRAND_LEAD),
        (Tier.CHANNEL, OwnerRole.CHANNEL_LEAD),
        (Tier.MARKET, OwnerRole.MARKET_LEAD),
    ],
)
def test_owner_role_for_each_tier(tier: Tier, role: OwnerRole) -> None:
    assert owner_role_for(tier) is role


def test_owner_role_for_is_a_bijection_over_tiers() -> None:
    assert {owner_role_for(tier) for tier in Tier} == set(OwnerRole)
