"""Tier definitions and owner-role registry for the governance hierarchy.

Defines the five-tier rule hierarchy in precedence order and the named owner
role responsible for each tier.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Tier(IntEnum):
    """A governance tier, ordered by authority.

    Members carry integer precedence values; a higher value means higher
    governance authority. ``ENTERPRISE`` is the highest tier and ``MARKET`` the
    lowest, so ``Tier.ENTERPRISE > Tier.MARKET`` is ``True``.
    """

    MARKET = 1
    CHANNEL = 2
    BRAND = 3
    FRANCHISE = 4
    ENTERPRISE = 5


class OwnerRole(Enum):
    """The named role accountable for governing rules at a given tier."""

    ENTERPRISE_LEAD = "Global Brand Governance Lead"
    FRANCHISE_LEAD = "Franchise Medical/Brand Lead"
    BRAND_LEAD = "Brand Lead"
    CHANNEL_LEAD = "Channel Operations Lead"
    MARKET_LEAD = "Market Compliance Lead"


_OWNER_ROLE_BY_TIER: dict[Tier, OwnerRole] = {
    Tier.ENTERPRISE: OwnerRole.ENTERPRISE_LEAD,
    Tier.FRANCHISE: OwnerRole.FRANCHISE_LEAD,
    Tier.BRAND: OwnerRole.BRAND_LEAD,
    Tier.CHANNEL: OwnerRole.CHANNEL_LEAD,
    Tier.MARKET: OwnerRole.MARKET_LEAD,
}


def owner_role_for(tier: Tier) -> OwnerRole:
    """Return the owner role accountable for the given tier."""
    return _OWNER_ROLE_BY_TIER[tier]
