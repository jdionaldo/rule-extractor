"""Rule stubs, conflicts, and conflict detection across the hierarchy."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .scope import Scope

# Statuses that count as "active or in-flight"; an existing rule in any of these
# states can participate in a conflict (i.e. anything except retired/withdrawn).
_IN_FLIGHT_STATUSES: frozenset[str] = frozenset(
    {"active", "draft", "approved_pending", "stuck"}
)


class RuleStub(BaseModel):
    """The minimal rule shape needed to reason about conflicts."""

    id: str
    scope: Scope
    subject: str
    status: Literal["active", "draft", "approved_pending", "stuck"]


class Conflict(BaseModel):
    """A detected conflict between a proposed rule and an existing rule."""

    proposed_id: str
    conflicting_id: str
    conflicting_scope: Scope
    severity: Literal["blocking", "supersedes", "subordinate"]


def detect_conflicts(
    proposed: RuleStub, existing: list[RuleStub]
) -> list[Conflict]:
    """Return the conflicts a proposed rule raises against existing rules.

    An existing rule conflicts with the proposed rule when it governs the same
    ``subject``, is active or in-flight, and its scope overlaps the proposed
    scope (one contains the other, or they are equal). Severity is determined by
    the relative tiers: ``blocking`` for the same tier (same scope),
    ``supersedes`` when the proposed rule sits at a higher tier, and
    ``subordinate`` when it sits at a lower tier.
    """
    conflicts: list[Conflict] = []
    for rule in existing:
        if rule.subject != proposed.subject:
            continue
        if rule.status not in _IN_FLIGHT_STATUSES:
            continue
        if not (
            proposed.scope.contains(rule.scope)
            or rule.scope.contains(proposed.scope)
        ):
            continue

        severity: Literal["blocking", "supersedes", "subordinate"]
        if proposed.scope.tier == rule.scope.tier:
            severity = "blocking"
        elif proposed.scope.tier > rule.scope.tier:
            severity = "supersedes"
        else:
            severity = "subordinate"

        conflicts.append(
            Conflict(
                proposed_id=proposed.id,
                conflicting_id=rule.id,
                conflicting_scope=rule.scope,
                severity=severity,
            )
        )
    return conflicts
