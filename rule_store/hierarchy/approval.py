"""Approval routing: which owner roles must sign off on a rule at a scope."""

from __future__ import annotations

from .scope import Scope
from .tiers import OwnerRole, Tier, owner_role_for

# The ancestor approval chain for each tier, highest authority first. CHANNEL
# and MARKET are sibling leaves under BRAND, so each routes up through
# BRAND -> FRANCHISE -> ENTERPRISE (not through one another).
_APPROVAL_CHAIN: dict[Tier, tuple[Tier, ...]] = {
    Tier.ENTERPRISE: (Tier.ENTERPRISE,),
    Tier.FRANCHISE: (Tier.ENTERPRISE, Tier.FRANCHISE),
    Tier.BRAND: (Tier.ENTERPRISE, Tier.FRANCHISE, Tier.BRAND),
    Tier.CHANNEL: (Tier.ENTERPRISE, Tier.FRANCHISE, Tier.BRAND, Tier.CHANNEL),
    Tier.MARKET: (Tier.ENTERPRISE, Tier.FRANCHISE, Tier.BRAND, Tier.MARKET),
}


def required_approvers(scope: Scope) -> list[OwnerRole]:
    """Return the owner roles required to approve a rule at this scope.

    The list runs from the highest tier down to the scope's own tier along its
    governance ancestor path. An ``ENTERPRISE`` rule needs only the Enterprise
    Lead; a ``BRAND`` rule needs Enterprise, Franchise, then Brand leads.
    """
    return [owner_role_for(tier) for tier in _APPROVAL_CHAIN[scope.tier]]
