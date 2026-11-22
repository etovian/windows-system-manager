"""Remediation execution engine and rollback management for sysmgr."""

from sysmgr.remediations.models import (
    RemediationContext,
    RemediationResult,
    RemediationScope,
    RollbackPlan,
)
from sysmgr.remediations.registry import (
    RemediationRegistry,
    default_remediation_registry,
    remediation_handler,
    remediation_rollback,
)
from sysmgr.remediations.rollback import RollbackManager
from sysmgr.remediations.runner import RemediationRunner
from sysmgr.remediations import handlers

__all__ = [
    "RemediationContext",
    "RemediationResult",
    "RemediationScope",
    "RollbackPlan",
    "RemediationRegistry",
    "default_remediation_registry",
    "remediation_handler",
    "remediation_rollback",
    "RollbackManager",
    "RemediationRunner",
    "handlers",
]
