from __future__ import annotations

import asyncio
from pathlib import Path

from services.watermark_service import apply_watermark

_processing_semaphore = asyncio.Semaphore(1)


async def apply_watermark_async(
    source_path: Path,
    destination_path: Path,
) -> None:
    async with _processing_semaphore:
        await asyncio.to_thread(apply_watermark, source_path, destination_path)
