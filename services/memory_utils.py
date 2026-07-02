from __future__ import annotations

import gc
import sys


def release_memory() -> None:
    gc.collect()
    if sys.platform != "linux":
        return

    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
