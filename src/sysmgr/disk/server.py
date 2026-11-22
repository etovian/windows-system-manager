"""Local Starlette HTTP server providing REST API and SSE endpoints for disk visualization."""

import asyncio
import os
from typing import Optional, Set
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from sysmgr.disk.actions import execute_file_action
from sysmgr.disk.drives import get_system_drives
from sysmgr.disk.models import ActionRequest, FileNode, ScanProgress
from sysmgr.disk.scanner import DiskScanner

# Global state trackers for active scan, latest progress telemetry, and scan hierarchy tree
_current_scan_tree: Optional[FileNode] = None
_latest_progress: Optional[ScanProgress] = None
_active_scanner: Optional[DiskScanner] = None
_scan_task: Optional[asyncio.Task] = None
_progress_queues: Set[asyncio.Queue] = set()


async def execute_scan(scanner: DiskScanner, target_path: str) -> None:
    """Run directory scanning asynchronously, dispatching progress events to active SSE streams."""
    global _current_scan_tree, _latest_progress
    loop = asyncio.get_running_loop()

    try:
        def on_progress(p: ScanProgress) -> None:
            global _latest_progress
            if scanner is not _active_scanner:
                return
            _latest_progress = p

            def notify() -> None:
                if scanner is not _active_scanner:
                    return
                for q in list(_progress_queues):
                    try:
                        q.put_nowait(p)
                    except Exception:
                        pass

            try:
                loop.call_soon_threadsafe(notify)
            except Exception:
                pass

        tree, _ = await scanner.scan(target_path, progress_callback=on_progress)
        if scanner is not _active_scanner:
            return

        _current_scan_tree = tree
        _latest_progress = ScanProgress(
            status="completed",
            current_path=target_path,
            files_scanned=_latest_progress.files_scanned if _latest_progress else 0,
            total_bytes=tree.size_bytes,
            elapsed_seconds=_latest_progress.elapsed_seconds if _latest_progress else 0.0,
        )

        for q in list(_progress_queues):
            try:
                q.put_nowait(_latest_progress)
            except Exception:
                pass

    except asyncio.CancelledError:
        if scanner is _active_scanner:
            _latest_progress = ScanProgress(
                status="failed",
                current_path=target_path,
                error_message="Scan cancelled",
            )
            for q in list(_progress_queues):
                try:
                    q.put_nowait(_latest_progress)
                except Exception:
                    pass
        raise

    except Exception as exc:
        if scanner is not _active_scanner:
            return
        _latest_progress = ScanProgress(
            status="failed",
            current_path=target_path,
            error_message=str(exc),
        )
        for q in list(_progress_queues):
            try:
                q.put_nowait(_latest_progress)
            except Exception:
                pass


async def get_drives(request: Request) -> JSONResponse:
    """Return mounted storage drive telemetry and capacity metrics."""
    drives = get_system_drives()
    return JSONResponse([drive.model_dump() for drive in drives])


async def start_scan(request: Request) -> JSONResponse:
    """Validate path and initiate asynchronous background directory scanning."""
    global _active_scanner, _scan_task, _latest_progress, _current_scan_tree

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not isinstance(payload, dict) or not isinstance(payload.get("path"), str) or not payload["path"].strip():
        return JSONResponse({"error": "Missing or invalid 'path' parameter"}, status_code=400)

    target_path = payload["path"]
    if not os.path.exists(target_path) or not os.path.isdir(target_path):
        return JSONResponse(
            {"error": f"Path '{target_path}' does not exist or is not a directory"},
            status_code=400,
        )

    target_path = os.path.abspath(target_path)

    # Abort previous scan if active
    if _active_scanner is not None:
        _active_scanner.cancel()
    if _scan_task is not None and not _scan_task.done():
        _scan_task.cancel()

    scanner = DiskScanner()
    _active_scanner = scanner
    _current_scan_tree = None
    _latest_progress = ScanProgress(
        status="scanning",
        current_path=target_path,
        files_scanned=0,
        total_bytes=0,
        elapsed_seconds=0.0,
    )

    _scan_task = asyncio.create_task(execute_scan(scanner, target_path))

    return JSONResponse({"status": "scan_started", "path": target_path})


async def cancel_scan(request: Request) -> JSONResponse:
    """Signal active directory scanner to abort in-flight traversal."""
    global _active_scanner, _scan_task
    if _active_scanner is not None:
        _active_scanner.cancel()
    if _scan_task is not None and not _scan_task.done():
        _scan_task.cancel()
    return JSONResponse({"status": "scan_cancelled"})


async def scan_progress_stream(request: Request) -> StreamingResponse:
    """Stream real-time directory scanning progress telemetry over Server-Sent Events (SSE)."""

    async def event_generator():
        q: asyncio.Queue[ScanProgress] = asyncio.Queue()
        _progress_queues.add(q)
        try:
            # Emit current snapshot immediately upon connection
            if _latest_progress is not None:
                yield f"data: {_latest_progress.model_dump_json()}\n\n"
                if _latest_progress.status in ("completed", "failed"):
                    return
            else:
                yield f"data: {ScanProgress(status='idle').model_dump_json()}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    prog = await asyncio.wait_for(q.get(), timeout=0.5)
                    yield f"data: {prog.model_dump_json()}\n\n"
                    if prog.status in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    if _latest_progress and _latest_progress.status in ("completed", "failed"):
                        yield f"data: {_latest_progress.model_dump_json()}\n\n"
                        break
                    yield ": keep-alive\n\n"
        finally:
            _progress_queues.discard(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def get_scan_tree(request: Request) -> JSONResponse:
    """Return aggregated directory tree hierarchy for visualizer rendering."""
    if _current_scan_tree is not None:
        return JSONResponse(_current_scan_tree.model_dump())
    return JSONResponse(None)


async def handle_actions(request: Request) -> JSONResponse:
    """Validate and execute file operation or remediation action."""
    try:
        body = await request.json()
        action_req = ActionRequest(**body)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    # Offload blocking file actions (e.g. powershell recycle) to worker thread
    result = await asyncio.to_thread(execute_file_action, action_req)
    return JSONResponse(result.model_dump())


def create_disk_app(web_dir: Optional[str] = None) -> Starlette:
    """Create and configure the Starlette application with REST routes, SSE, and static assets."""
    routes = [
        Route("/api/drives", get_drives, methods=["GET"]),
        Route("/api/scan", start_scan, methods=["POST"]),
        Route("/api/scan/cancel", cancel_scan, methods=["POST"]),
        Route("/api/scan/progress", scan_progress_stream, methods=["GET"]),
        Route("/api/scan/tree", get_scan_tree, methods=["GET"]),
        Route("/api/actions", handle_actions, methods=["POST"]),
    ]

    static_path = web_dir or os.path.join(os.path.dirname(__file__), "web")
    if os.path.exists(static_path) and os.path.isdir(static_path):
        routes.append(Mount("/", StaticFiles(directory=static_path, html=True), name="web"))

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]

    app = Starlette(debug=False, routes=routes, middleware=middleware)
    return app
