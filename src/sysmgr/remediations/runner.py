from typing import Optional
from sysmgr.core.engine import ProbeEngine
from sysmgr.probes import create_default_engine
from sysmgr.remediations.models import (
    RemediationContext,
    RemediationResult,
    RemediationScope,
)
from sysmgr.remediations.registry import RemediationRegistry, default_remediation_registry
from sysmgr.remediations.rollback import RollbackManager


class RemediationRunner:
    def __init__(
        self,
        registry: Optional[RemediationRegistry] = None,
        rollback_manager: Optional[RollbackManager] = None,
        probe_engine: Optional[ProbeEngine] = None,
    ):
        self.registry = registry or default_remediation_registry
        self.rollback_manager = rollback_manager or RollbackManager()
        self.probe_engine = probe_engine or create_default_engine()

    async def execute(self, action_id: str, ctx: RemediationContext) -> RemediationResult:
        handler_entry = self.registry.get(action_id)
        if not handler_entry:
            return RemediationResult(
                action_id=action_id,
                success=False,
                error=f"No remediation registered for '{action_id}'.",
            )

        # Dry run simulation
        if ctx.dry_run:
            return RemediationResult(
                action_id=action_id,
                success=True,
                changes_made=[f"[DRY RUN] Would execute {handler_entry.description} (Scope: {handler_entry.scope.value})"],
            )

        # Persistent action: Generate and commit rollback plan (fail closed if missing)
        rollback_file_path = None
        if handler_entry.scope == RemediationScope.PERSISTENT:
            if not handler_entry.rollback_generator:
                return RemediationResult(
                    action_id=action_id,
                    success=False,
                    error=(
                        f"Persistent remediation '{action_id}' requires a registered rollback generator "
                        "before execution to prevent unrecoverable system alterations."
                    ),
                )
            try:
                plan = await handler_entry.rollback_generator()
                saved_path = self.rollback_manager.save_and_commit(plan)
                rollback_file_path = str(saved_path)
            except Exception as e:
                return RemediationResult(
                    action_id=action_id,
                    success=False,
                    error=f"Rollback plan creation failed: {e}. Remediation aborted for safety.",
                )

        # Execute handler behind safety barrier
        try:
            changes = await handler_entry.handler(ctx)
        except Exception as e:
            return RemediationResult(
                action_id=action_id,
                success=False,
                error=f"Remediation execution failed: {e}",
                rollback_file=rollback_file_path,
            )

        # Post-check verification if parent probe is registered
        post_check_result = None
        if handler_entry.parent_probe_id:
            probe = self.probe_engine.get_probe(handler_entry.parent_probe_id)
            if probe:
                post_check_result = await self.probe_engine.run_probe(probe)

        return RemediationResult(
            action_id=action_id,
            success=True,
            changes_made=changes,
            rollback_file=rollback_file_path,
            post_check=post_check_result,
        )
