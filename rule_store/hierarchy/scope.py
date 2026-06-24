"""The Scope model: tier placement, validation, containment, and precedence."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from .tiers import Tier

# The defining fields for each tier: the ancestor-path discriminators that must
# be present for a scope at that tier, and the fields used to test containment.
# A field is required for a tier exactly when it appears in that tier's tuple.
_DEFINING_FIELDS: dict[Tier, tuple[str, ...]] = {
    Tier.ENTERPRISE: (),
    Tier.FRANCHISE: ("franchise",),
    Tier.BRAND: ("franchise", "brand"),
    Tier.CHANNEL: ("franchise", "brand", "channel"),
    Tier.MARKET: ("franchise", "brand", "market"),
}


class Scope(BaseModel):
    """The governance scope a rule belongs to.

    A scope names its ``tier`` plus the ancestor-path discriminators required at
    that tier (validated at construction). Scopes form a tree: ``ENTERPRISE`` is
    the root; ``FRANCHISE`` sits under it; ``BRAND`` under a franchise; and
    ``CHANNEL`` and ``MARKET`` are sibling leaves under a brand.
    """

    tier: Tier
    franchise: str | None = None
    brand: str | None = None
    channel: str | None = None
    market: str | None = None

    @model_validator(mode="after")
    def _require_fields_for_tier(self) -> Scope:
        """Reject construction when a field required by the tier is missing."""
        for field in _DEFINING_FIELDS[self.tier]:
            if getattr(self, field) is None:
                raise ValueError(
                    f"{self.tier.name} scope requires '{field}' to be set."
                )
        return self

    def contains(self, other: Scope) -> bool:
        """Return True if this scope is broader than or equal to ``other``.

        A scope contains another when every discriminator that defines this
        scope matches the corresponding field on the other scope. ``ENTERPRISE``
        (which has no discriminators) contains every scope; a ``BRAND`` scope
        contains the ``CHANNEL`` and ``MARKET`` scopes beneath that same brand,
        but nothing beneath a different brand.
        """
        return all(
            getattr(self, field) == getattr(other, field)
            for field in _DEFINING_FIELDS[self.tier]
        )

    def outranks(self, other: Scope) -> bool:
        """Return True if this scope has strictly higher authority than ``other``.

        True only when the two scopes overlap (one contains the other) and this
        scope sits at a higher-precedence tier.
        """
        overlaps = self.contains(other) or other.contains(self)
        return self.tier > other.tier and overlaps
