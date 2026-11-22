from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Optional
from sysmgr.core.models import RiskLevel
from sysmgr.remediations.models import RemediationContext, RemediationScope, RollbackPlan

HandlerFunc = Callable[[RemediationContext], Coroutine[Any, Any, List[str]]]
RollbackPlanFunc = Callable[[], Coroutine[Any, Any, RollbackPlan]]


@dataclass
class RegisteredHandler:
    action_id: str
    description: str
    scope: RemediationScope
    risk_level: RiskLevel
    requires_admin: bool
    parent_probe_id: Optional[str]
    handler: HandlerFunc
    rollback_generator: Optional[RollbackPlanFunc] = None


class RemediationRegistry:
    def __init__(self):
        self._handlers: Dict[str, RegisteredHandler] = {}

    def register(
        self,
        action_id: str,
        description: str,
        scope: RemediationScope = RemediationScope.TRANSIENT,
        risk_level: RiskLevel = RiskLevel.SAFE,
        requires_admin: bool = False,
        parent_probe_id: Optional[str] = None,
    ):
        def decorator(fn: HandlerFunc):
            self._handlers[action_id] = RegisteredHandler(
                action_id=action_id,
                description=description,
                scope=scope,
                risk_level=risk_level,
                requires_admin=requires_admin,
                parent_probe_id=parent_probe_id,
                handler=fn,
            )
            return fn
        return decorator

    def register_rollback(self, action_id: str):
        def decorator(fn: RollbackPlanFunc):
            if action_id in self._handlers:
                self._handlers[action_id].rollback_generator = fn
            return fn
        return decorator

    def get(self, action_id: str) -> Optional[RegisteredHandler]:
        return self._handlers.get(action_id)

    def list_all(self) -> Dict[str, RegisteredHandler]:
        return dict(self._handlers)


# Global default registry instance
default_remediation_registry = RemediationRegistry()
remediation_handler = default_remediation_registry.register
remediation_rollback = default_remediation_registry.register_rollback
