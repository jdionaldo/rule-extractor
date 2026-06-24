"""Tests for RuleStub, Conflict, and detect_conflicts."""

from __future__ import annotations

from typing import Literal

import pytest

from rule_store.hierarchy import RuleStub, Scope, Tier, detect_conflicts

_SUBJECT = "meta.image.dimensions"

Status = Literal["active", "draft", "approved_pending", "stuck"]


def _rule(
    rule_id: str,
    scope: Scope,
    *,
    subject: str = _SUBJECT,
    status: Status = "active",
) -> RuleStub:
    return RuleStub(id=rule_id, scope=scope, subject=subject, status=status)


def test_same_tier_same_scope_is_blocking(brand_scope: Scope) -> None:
    conflicts = detect_conflicts(
        _rule("P", brand_scope), [_rule("E", brand_scope)]
    )
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.severity == "blocking"
    assert conflict.proposed_id == "P"
    assert conflict.conflicting_id == "E"
    assert conflict.conflicting_scope == brand_scope


def test_proposed_higher_tier_supersedes(
    brand_scope: Scope, market_scope: Scope
) -> None:
    conflicts = detect_conflicts(
        _rule("P", brand_scope), [_rule("E", market_scope)]
    )
    assert [c.severity for c in conflicts] == ["supersedes"]


def test_proposed_lower_tier_is_subordinate(
    brand_scope: Scope, market_scope: Scope
) -> None:
    conflicts = detect_conflicts(
        _rule("P", market_scope), [_rule("E", brand_scope)]
    )
    assert [c.severity for c in conflicts] == ["subordinate"]


def test_enterprise_supersedes_all_lower_overlapping(
    enterprise_scope: Scope, channel_scope: Scope, market_scope: Scope
) -> None:
    conflicts = detect_conflicts(
        _rule("P", enterprise_scope),
        [_rule("E1", channel_scope), _rule("E2", market_scope)],
    )
    assert len(conflicts) == 2
    assert {c.severity for c in conflicts} == {"supersedes"}


def test_no_conflict_for_different_subject(brand_scope: Scope) -> None:
    conflicts = detect_conflicts(
        _rule("P", brand_scope, subject="a.b.c"),
        [_rule("E", brand_scope, subject="x.y.z")],
    )
    assert conflicts == []


def test_no_conflict_for_non_overlapping_scopes() -> None:
    brand_x = Scope(tier=Tier.BRAND, franchise="Onco", brand="BrandX")
    brand_y = Scope(tier=Tier.BRAND, franchise="Onco", brand="BrandY")
    conflicts = detect_conflicts(_rule("P", brand_x), [_rule("E", brand_y)])
    assert conflicts == []


def test_no_conflict_between_sibling_scopes(
    channel_scope: Scope, market_scope: Scope
) -> None:
    conflicts = detect_conflicts(
        _rule("P", channel_scope), [_rule("E", market_scope)]
    )
    assert conflicts == []


@pytest.mark.parametrize(
    "status", ["active", "draft", "approved_pending", "stuck"]
)
def test_every_in_flight_status_conflicts(
    brand_scope: Scope, status: Status
) -> None:
    conflicts = detect_conflicts(
        _rule("P", brand_scope), [_rule("E", brand_scope, status=status)]
    )
    assert len(conflicts) == 1


def test_empty_existing_yields_no_conflicts(brand_scope: Scope) -> None:
    assert detect_conflicts(_rule("P", brand_scope), []) == []


def test_only_matching_existing_rules_conflict(
    brand_scope: Scope, market_scope: Scope
) -> None:
    existing = [
        _rule("same", brand_scope),
        _rule("other-subject", brand_scope, subject="unrelated"),
        _rule("narrower", market_scope),
    ]
    conflicts = detect_conflicts(_rule("P", brand_scope), existing)
    by_id = {c.conflicting_id: c.severity for c in conflicts}
    assert by_id == {"same": "blocking", "narrower": "supersedes"}
