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


def is_user_admin() -> bool:
    """Check if current process has elevated Administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


class RemediationRunner:
    def __init__(
        self,
        registry: Optional[RemediationRegistry] = None,
        rollback_manager: Optional[RollbackManager] = None,
        probe_engine: Optional[ProbeEngine] = None,
        admin_check_fn: Optional[callable] = None,
    ):
        self.registry = registry or default_remediation_registry
        self.rollback_manager = rollback_manager or RollbackManager()
        self.probe_engine = probe_engine or create_default_engine()
        self.admin_check_fn = admin_check_fn or is_user_admin

    async def execute(self, action_id: str, ctx: RemediationContext) -> RemediationResult:
        handler_entry = self.registry.get(action_id)
        if not handler_entry:
            return RemediationResult(
                action_id=action_id,
                success=False,
                error=f"No remediation registered for '{action_id}'.",
            )

        # Pre-flight check: verify Administrator status upfront if action requires admin
        if handler_entry.requires_admin and not ctx.dry_run and not ctx.elevated:
            if not self.admin_check_fn():
                return RemediationResult(
                    action_id=action_id,
                    success=False,
                    error=f"Remediation '{action_id}' requires elevated Administrator privileges.",
                )

        # Dry run simulation (executes handler simulation logic without side-effects or rollback)
        if ctx.dry_run:
            try:
                changes = await handler_entry.handler(ctx)
                formatted_changes = []
                for chg in changes:
                    if chg.lower().startswith("[dry run]"):
                        clean_chg = chg[len("[dry run]"):].strip()
                        formatted_changes.append(f"[DRY RUN] [{handler_entry.scope.value}] {clean_chg}")
                    else:
                        formatted_changes.append(f"[DRY RUN] [{handler_entry.scope.value}] {chg}")
                if not formatted_changes:
                    formatted_changes = [f"[DRY RUN] [{handler_entry.scope.value}] Would execute {handler_entry.description}"]
                return RemediationResult(
                    action_id=action_id,
                    success=True,
                    changes_made=formatted_changes,
                )
            except Exception as e:
                return RemediationResult(
                    action_id=action_id,
                    success=False,
                    error=f"Dry-run simulation failed: {e}",
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
