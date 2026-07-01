from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from services.watermark_service import WatermarkError, release_memory

_processing_semaphore = asyncio.Semaphore(1)
_WATERMARK_TIMEOUT_SECONDS = 120


def _run_watermarks_subprocess(pairs: list[tuple[Path, Path]]) -> None:
    if not pairs:
        return

    arguments = [sys.executable, "-m", "services.watermark_worker"]
    for source_path, destination_path in pairs:
        arguments.extend((str(source_path), str(destination_path)))

    timeout = max(_WATERMARK_TIMEOUT_SECONDS, 60 * len(pairs))
    try:
        subprocess.run(
            arguments,
            check=True,
            timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise WatermarkError("Failed to process image") from exc


async def apply_watermarks_batch_async(
    pairs: list[tuple[Path, Path]],
) -> None:
    if not pairs:
        return

    async with _processing_semaphore:
        await asyncio.to_thread(_run_watermarks_subprocess, pairs)


async def release_memory_async() -> None:
    await asyncio.to_thread(release_memory)
