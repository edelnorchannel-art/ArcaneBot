from __future__ import annotations

import sys
from pathlib import Path

from services.watermark_errors import WatermarkError
from services.watermark_service import apply_watermark


def main() -> None:
    arguments = sys.argv[1:]
    if len(arguments) < 2 or len(arguments) % 2 != 0:
        raise SystemExit("Usage: python -m services.watermark_worker <src> <dst> [<src> <dst> ...]")

    for source_argument, destination_argument in zip(
        arguments[0::2],
        arguments[1::2],
        strict=True,
    ):
        try:
            apply_watermark(Path(source_argument), Path(destination_argument))
        except WatermarkError:
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
