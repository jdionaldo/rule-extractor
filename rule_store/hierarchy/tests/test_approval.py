"""Tests for approval routing."""

from __future__ import annotations

from rule_store.hierarchy import OwnerRole, Scope, required_approvers


def test_enterprise_requires_only_enterprise_lead(
    enterprise_scope: Scope,
) -> None:
    assert required_approvers(enterprise_scope) == [OwnerRole.ENTERPRISE_LEAD]


def test_franchise_chain(franchise_scope: Scope) -> None:
    assert required_approvers(franchise_scope) == [
        OwnerRole.ENTERPRISE_LEAD,
        OwnerRole.FRANCHISE_LEAD,
    ]


def test_brand_chain(brand_scope: Scope) -> None:
    assert required_approvers(brand_scope) == [
        OwnerRole.ENTERPRISE_LEAD,
        OwnerRole.FRANCHISE_LEAD,
        OwnerRole.BRAND_LEAD,
    ]


def test_channel_chain(channel_scope: Scope) -> None:
    assert required_approvers(channel_scope) == [
        OwnerRole.ENTERPRISE_LEAD,
        OwnerRole.FRANCHISE_LEAD,
        OwnerRole.BRAND_LEAD,
        OwnerRole.CHANNEL_LEAD,
    ]


def test_market_chain_routes_through_brand_not_channel(
    market_scope: Scope,
) -> None:
    assert required_approvers(market_scope) == [
        OwnerRole.ENTERPRISE_LEAD,
        OwnerRole.FRANCHISE_LEAD,
        OwnerRole.BRAND_LEAD,
        OwnerRole.MARKET_LEAD,
    ]


def test_chain_is_ordered_highest_to_lowest(channel_scope: Scope) -> None:
    approvers = required_approvers(channel_scope)
    assert approvers[0] is OwnerRole.ENTERPRISE_LEAD
    assert approvers[-1] is OwnerRole.CHANNEL_LEAD
