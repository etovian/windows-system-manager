"""Multi-threaded streaming directory scanner with size aggregation and loop protection."""

import asyncio
import os
import time
from typing import Callable, List, Optional, Tuple

from sysmgr.disk.models import FileNode, ScanProgress


class DiskScanner:
    """Bottom-up directory scanner that computes sizes and emits throttled progress updates."""

    def __init__(self, min_size_ratio: float = 0.005, max_depth: int = 10) -> None:
        self.min_size_ratio = min_size_ratio
        self.max_depth = max_depth
        self.is_cancelled = False

    def cancel(self) -> None:
        """Signal the scanner to abort any in-progress directory traversal."""
        self.is_cancelled = True

    def reset(self) -> None:
        """Reset scanner cancellation state for reuse."""
        self.is_cancelled = False

    async def scan(
        self,
        target_path: str,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
    ) -> Tuple[FileNode, List[ScanProgress]]:
        """Traverse target_path, aggregate disk usage bottom-up, and emit progress events.

        Runs synchronous filesystem traversal in the default loop executor to keep the
        asyncio event loop responsive. Note: progress_callback is invoked synchronously
        from worker threads in the executor pool.
        """
        target_path = os.path.abspath(target_path)
        progress_history: List[ScanProgress] = []
        files_scanned = 0
        total_bytes = 0
        start_time = time.time()
        last_progress_time = 0.0

        def emit_progress(
            curr_path: str,
            status: str = "scanning",
            error_message: Optional[str] = None,
        ) -> None:
            nonlocal last_progress_time
            now = time.time()
            if now - last_progress_time >= 0.1 or status != "scanning":
                last_progress_time = now
                p = ScanProgress(
                    status=status,  # type: ignore[arg-type]
                    current_path=curr_path,
                    files_scanned=files_scanned,
                    total_bytes=total_bytes,
                    elapsed_seconds=round(now - start_time, 2),
                    error_message=error_message,
                )
                progress_history.append(p)
                if progress_callback:
                    progress_callback(p)

        def scan_dir(dir_path: str, depth: int) -> FileNode:
            nonlocal files_scanned, total_bytes
            if self.is_cancelled or depth > self.max_depth:
                return FileNode(
                    name=os.path.basename(dir_path) or dir_path,
                    path=dir_path,
                    is_dir=True,
                    size_bytes=0,
                )

            emit_progress(dir_path)

            children: List[FileNode] = []
            dir_total = 0

            try:
                with os.scandir(dir_path) as it:
                    entries = list(it)
            except (PermissionError, OSError):
                return FileNode(
                    name=os.path.basename(dir_path) or dir_path,
                    path=dir_path,
                    size_bytes=0,
                    is_dir=True,
                )

            for entry in entries:
                if self.is_cancelled:
                    break
                try:
                    # Skip symlinks/reparse points to avoid loops
                    is_symlink = entry.is_symlink()
                    is_junction = getattr(entry, "is_junction", None)
                    if is_symlink or (callable(is_junction) and is_junction()):
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        child_node = scan_dir(entry.path, depth + 1)
                        dir_total += child_node.size_bytes
                        children.append(child_node)
                    else:
                        stat = entry.stat(follow_symlinks=False)
                        size = stat.st_size
                        files_scanned += 1
                        total_bytes += size
                        dir_total += size
                        children.append(
                            FileNode(
                                name=entry.name,
                                path=entry.path,
                                size_bytes=size,
                                is_dir=False,
                            )
                        )
                    if files_scanned % 50 == 0:
                        emit_progress(entry.path)
                except (PermissionError, OSError):
                    continue

            # Sort children descending by size
            children.sort(key=lambda c: c.size_bytes, reverse=True)

            # Roll up small items into "Other files" if above threshold
            if dir_total > 0 and len(children) > 5:
                threshold = dir_total * self.min_size_ratio
                primary_children: List[FileNode] = []
                other_size = 0
                for c in children:
                    if c.size_bytes < threshold:
                        other_size += c.size_bytes
                    else:
                        primary_children.append(c)

                # Ensure at least the top 3 items remain unrolled so directory isn't completely opaque
                if not primary_children and len(children) > 3:
                    primary_children = children[:3]
                    other_size = sum(c.size_bytes for c in children[3:])

                if other_size > 0:
                    primary_children.append(
                        FileNode(
                            name="Other files",
                            path=os.path.join(dir_path, "_other_"),
                            size_bytes=other_size,
                            is_dir=False,
                        )
                    )
                children = primary_children

            return FileNode(
                name=os.path.basename(dir_path) or dir_path,
                path=dir_path,
                size_bytes=dir_total,
                is_dir=True,
                children=children,
            )

        emit_progress(target_path, "scanning")

        if os.path.isfile(target_path):
            try:
                stat = os.stat(target_path)
                size = stat.st_size
                files_scanned += 1
                total_bytes += size
            except (PermissionError, OSError):
                size = 0
            emit_progress(target_path, "completed")
            return (
                FileNode(
                    name=os.path.basename(target_path),
                    path=target_path,
                    size_bytes=size,
                    is_dir=False,
                ),
                progress_history,
            )

        loop = asyncio.get_running_loop()
        try:
            root_node = await loop.run_in_executor(None, scan_dir, target_path, 0)
            emit_progress(target_path, "completed")
            return root_node, progress_history
        except Exception as exc:
            emit_progress(target_path, "failed", error_message=str(exc))
            raise
