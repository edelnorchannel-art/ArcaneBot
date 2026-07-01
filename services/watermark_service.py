from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

logger = logging.getLogger(__name__)

WATERMARK_PATH = Path(__file__).resolve().parents[1] / "imgs" / "watermark.png"
WATERMARK_WIDTH_RATIO = 0.15
WATERMARK_MARGIN = 20
JPEG_QUALITY = 90


class WatermarkError(Exception):
    pass


def apply_watermark(source_path: Path, destination_path: Path) -> None:
    if not WATERMARK_PATH.is_file():
        raise WatermarkError(f"Watermark file not found: {WATERMARK_PATH}")

    try:
        with Image.open(source_path) as photo:
            photo = ImageOps.exif_transpose(photo)
            photo = photo.convert("RGBA")

            with Image.open(WATERMARK_PATH) as logo:
                logo = logo.convert("RGBA")
                logo_width = max(1, int(photo.width * WATERMARK_WIDTH_RATIO))
                ratio = logo_width / logo.width
                logo_height = max(1, int(logo.height * ratio))
                logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

                position = (
                    WATERMARK_MARGIN,
                    photo.height - logo_height - WATERMARK_MARGIN,
                )
                photo.paste(logo, position, logo)

            photo.convert("RGB").save(
                destination_path,
                "JPEG",
                quality=JPEG_QUALITY,
            )
    except WatermarkError:
        raise
    except Exception as exc:
        logger.exception("Failed to apply watermark to %s", source_path)
        raise WatermarkError("Failed to process image") from exc
