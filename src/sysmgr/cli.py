import asyncio
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import sysmgr
from sysmgr.core.models import DiagnosticStatus
from sysmgr.probes import create_default_engine
from sysmgr.remediations import (
    RemediationContext,
    RemediationResult,
    RemediationRunner,
    RemediationScope,
    default_remediation_registry,
)

app = typer.Typer(
    name="sysmgr",
    help="Agent-integrated Windows system utilities, health diagnostics, and management.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"sysmgr version: {sysmgr.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show sysmgr version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    pass


@app.command()
def doctor(
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter diagnostics by category (hardware, storage, readiness).",
    ),
    timeout: float = typer.Option(
        15.0,
        "--timeout",
        "-t",
        help="Maximum timeout in seconds per probe (default: 15.0s).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output raw machine-readable JSON format for agents and scripts.",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Interactively execute available remediations for warnings/failures.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically accept confirmation prompts.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run remediations in simulation dry-run mode.",
    ),
):
    """Run system diagnostic probes across hardware, storage, and upgrade readiness."""
    engine = create_default_engine(probe_timeout_seconds=timeout)
    report = asyncio.run(engine.run_all(category=category))

    if fix and json_output:
        console.print("[red]Error:[/red] The '--fix' and '--json' options cannot be combined. Use 'sysmgr fix <action_id> --json' for machine-readable remediation.")
        raise typer.Exit(code=1)

    if json_output:
        print(report.model_dump_json(indent=2))
        return

    # Terminal Rich Presentation
    console.print()
    console.print(Panel.fit(
        f"[bold blue]sysmgr System Doctor[/bold blue] | Category: [cyan]{category or 'ALL'}[/cyan]\n"
        f"Timestamp: [dim]{report.timestamp}[/dim] | Probes: {report.total_probes} total "
        f"([green]{report.pass_count} PASS[/green], [yellow]{report.warn_count} WARN[/yellow], [red]{report.fail_count} FAIL[/red])",
        title="Diagnostic Report",
    ))

    table = Table(title="Diagnostic Probes", show_lines=True)
    table.add_column("Status", justify="center", style="bold", width=8)
    table.add_column("Category", style="cyan", width=12)
    table.add_column("Probe ID", style="bold white", width=25)
    table.add_column("Findings & Remediation", style="white")

    for res in report.results:
        if res.status == DiagnosticStatus.PASS:
            status_badge = "[green]PASS[/green]"
        elif res.status == DiagnosticStatus.WARN:
            status_badge = "[yellow]WARN[/yellow]"
        elif res.status == DiagnosticStatus.FAIL:
            status_badge = "[red]FAIL[/red]"
        else:
            status_badge = "[blue]INFO[/blue]"

        details_text = f"{res.summary}"
        if res.remediations:
            details_text += "\n[bold yellow]Available Remediations:[/bold yellow]"
            for rem in res.remediations:
                admin_tag = " [bold red](Admin)[/bold red]" if rem.requires_admin else ""
                details_text += f"\n  • [bold]{rem.id}[/bold]: {rem.description}{admin_tag}"

        table.add_row(status_badge, res.category, res.probe_id, details_text)

    console.print(table)
    console.print()

    if fix:
        remediations_to_apply = []
        seen_ids = set()
        for res in report.results:
            if res.status in (DiagnosticStatus.WARN, DiagnosticStatus.FAIL) and res.remediations:
                for rem in res.remediations:
                    if rem.id not in seen_ids:
                        seen_ids.add(rem.id)
                        remediations_to_apply.append(rem)

        if not remediations_to_apply:
            console.print("[bold green]No remediations required.[/bold green]")
            if report.fail_count > 0:
                raise typer.Exit(code=1)
            return

        console.print(f"[bold yellow]Found {len(remediations_to_apply)} available remediation(s):[/bold yellow]")
        for rem in remediations_to_apply:
            handler_entry = default_remediation_registry.get(rem.id)
            scope_badge = f" [cyan][{handler_entry.scope.value}][/cyan]" if handler_entry else ""
            admin_tag = " [bold red](Admin)[/bold red]" if rem.requires_admin else ""
            console.print(f"  • [bold]{rem.id}[/bold]: {rem.description}{scope_badge}{admin_tag}")
        console.print()

        if not yes:
            if not typer.confirm(f"Apply {len(remediations_to_apply)} remediation(s)?", default=False):
                console.print("[yellow]Remediation cancelled by user.[/yellow]")
                if report.fail_count > 0:
                    raise typer.Exit(code=1)
                return

        runner = RemediationRunner()
        all_success = True
        for rem in remediations_to_apply:
            console.print(f"\n[bold]Executing remediation '{rem.id}'...[/bold]")
            ctx = RemediationContext(dry_run=dry_run, auto_confirm=True)
            rem_res = asyncio.run(runner.execute(rem.id, ctx=ctx))
            if rem_res.success:
                console.print(f"[green]SUCCESS[/green] [bold]{rem.id}[/bold]")
                for change in rem_res.changes_made:
                    console.print(f"  • {change}")
                if rem_res.rollback_file:
                    console.print(f"  [bold cyan]Rollback Plan:[/bold cyan] {rem_res.rollback_file}")
                if rem_res.post_check:
                    post_color = "green" if rem_res.post_check.status == DiagnosticStatus.PASS else "yellow" if rem_res.post_check.status == DiagnosticStatus.WARN else "red"
                    console.print(f"  Post-Check: [{post_color}][{rem_res.post_check.status.value}][/{post_color}] {rem_res.post_check.summary}")
            else:
                all_success = False
                console.print(f"[red]FAILED[/red] [bold]{rem.id}[/bold]: {rem_res.error}")

        console.print()
        if not all_success:
            raise typer.Exit(code=1)
        return

    if report.fail_count > 0:
        raise typer.Exit(code=1)


@app.command()
def fix(
    action_id: str = typer.Argument(..., help="Unique ID of remediation action to execute."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate changes without modifying system state."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt for persistent alterations."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Execute a remediation action by unique action ID."""
    runner = RemediationRunner()
    handler = default_remediation_registry.get(action_id)
    if not handler:
        if json_output:
            failure_result = RemediationResult(
                action_id=action_id,
                success=False,
                error=f"No remediation registered for '{action_id}'.",
            )
            print(failure_result.model_dump_json(indent=2))
        else:
            console.print(f"[red]Error:[/red] No remediation registered for '{action_id}'.")
        raise typer.Exit(code=1)

    if handler.scope == RemediationScope.PERSISTENT and not dry_run and not yes:
        if json_output:
            unconfirmed_result = RemediationResult(
                action_id=action_id,
                success=False,
                error="Persistent remediation requires explicit confirmation. Pass '--yes' or use '--dry-run'.",
            )
            print(unconfirmed_result.model_dump_json(indent=2))
            raise typer.Exit(code=1)

        if not typer.confirm(f"Confirm executing persistent remediation '{action_id}'?", default=False):
            console.print("[yellow]Remediation cancelled by user.[/yellow]")
            return

    ctx = RemediationContext(dry_run=dry_run, auto_confirm=yes)
    result = asyncio.run(runner.execute(action_id, ctx=ctx))

    if json_output:
        print(result.model_dump_json(indent=2))
        if not result.success:
            raise typer.Exit(code=1)
        return

    # Rich presentation
    status_badge = "[bold green]SUCCESS[/bold green]" if result.success else "[bold red]FAILED[/bold red]"
    panel_content = f"Status: {status_badge}\nAction ID: [bold]{result.action_id}[/bold]"
    if result.changes_made:
        panel_content += "\n\nChanges Made:\n" + "\n".join(f"  • {c}" for c in result.changes_made)
    if result.error:
        panel_content += f"\n\n[bold red]Error:[/bold red] {result.error}"

    console.print()
    console.print(Panel.fit(panel_content, title="Remediation Execution"))

    if result.rollback_file:
        console.print(f"[bold cyan]Rollback Plan:[/bold cyan] {result.rollback_file}")

    if result.post_check:
        post_color = "green" if result.post_check.status == DiagnosticStatus.PASS else "yellow" if result.post_check.status == DiagnosticStatus.WARN else "red"
        console.print(f"Post-Check: [{post_color}][{result.post_check.status.value}][/{post_color}] {result.post_check.summary}")

    console.print()
    if not result.success:
        raise typer.Exit(code=1)


@app.command()
def check(
    probe_id: str = typer.Argument(..., help="Unique ID of probe to run (e.g. hardware.bluetooth)."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Run an individual diagnostic probe by ID."""
    engine = create_default_engine()
    probe = engine.get_probe(probe_id)
    if not probe:
        console.print(f"[red]Error:[/red] Probe '{probe_id}' not found.")
        raise typer.Exit(code=1)

    result = asyncio.run(engine.run_probe(probe))

    if json_output:
        print(result.model_dump_json(indent=2))
        return

    color = "green" if result.status == DiagnosticStatus.PASS else "yellow" if result.status == DiagnosticStatus.WARN else "red"
    console.print(f"[{color}][{result.status.value}][/{color}] [bold]{result.probe_id}[/bold]: {result.summary}")
    if result.remediations:
        console.print("\n[bold]Remediations:[/bold]")
        for r in result.remediations:
            console.print(f" - {r.id}: {r.description} ({r.risk_level.value})")


@app.command()
def knowledge(
    runbook: Optional[str] = typer.Argument(None, help="Specific runbook name or topic to display."),
):
    """Browse or read troubleshooting runbooks and decision playbooks."""
    knowledge_dir = Path("knowledge")
    if not knowledge_dir.exists():
        console.print("[yellow]Knowledge directory not found.[/yellow]")
        return

    md_files = list(knowledge_dir.glob("**/*.md"))

    if not runbook:
        table = Table(title="Troubleshooting Runbooks & Decision Playbooks")
        table.add_column("Subsystem", style="cyan")
        table.add_column("Runbook File", style="white")

        for f in md_files:
            subsystem = f.parent.name
            table.add_row(subsystem, f.name)

        console.print(table)
        console.print("\n[dim]Run `sysmgr knowledge <filename>` to view a specific runbook.[/dim]")
        return

    # Search for matching file
    match = next((f for f in md_files if runbook.lower() in f.name.lower()), None)
    if not match:
        console.print(f"[red]No runbook found matching '{runbook}'.[/red]")
        raise typer.Exit(code=1)

    content = match.read_text(encoding="utf-8")
    console.print(Panel(content, title=f"Runbook: {match.name}", border_style="cyan"))


if __name__ == "__main__":
    app()
