# System Rollback Plans Directory

This directory stores mandatory, executable rollback plans created before any system settings, services, drivers, or registry configurations are altered.

## Standard Rollback Plan Structure

Every rollback plan must be saved as `docs/rollback/YYYY-MM-DD-<topic>-rollback.md` and include:

1. **Change Summary**: What system settings, services, drivers, or registry keys will be modified.
2. **Pre-Change Baseline State**: Exact snapshot of existing values before the modification.
3. **Automated Rollback Commands (Agent-Executable)**: Copy-pasteable or scriptable commands the AI agent can execute to reverse the change.
4. **Manual Safe Mode / Recovery Console Instructions**: Step-by-step instructions for human execution in Windows Safe Mode, WinPE, or Command Prompt if Windows cannot boot or networking is lost.
5. **Post-Rollback Verification**: Commands to confirm the system has successfully returned to its baseline state.
