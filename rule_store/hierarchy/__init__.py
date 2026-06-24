"""Governance hierarchy for the Rule Store.

Public API for the five-tier rule hierarchy: tier/owner definitions, the scope
model with validation and precedence, conflict detection, and approval routing.
"""

from __future__ import annotations

from .approval import required_approvers
from .conflicts import Conflict, RuleStub, detect_conflicts
from .scope import Scope
from .tiers import OwnerRole, Tier, owner_role_for

__all__ = [
    "Tier",
    "OwnerRole",
    "owner_role_for",
    "Scope",
    "RuleStub",
    "Conflict",
    "detect_conflicts",
    "required_approvers",
]
