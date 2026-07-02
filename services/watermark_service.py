from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

from services.memory_utils import release_memory
from services.watermark_errors import WatermarkError

logger = logging.getLogger(__name__)

WATERMARK_PATH = Path(__file__).resolve().parents[1] / "imgs" / "watermark.png"
WATERMARK_HEIGHT_RATIO = 1 / 8
WATERMARK_WIDTH_RATIO_VERTICAL = 1 / 3
WATERMARK_MARGIN = 20
JPEG_QUALITY = 90


def _detach_image(image: Image.Image, opened_image: Image.Image) -> Image.Image:
    if image is opened_image:
        return image.copy()
    return image


def _replace_image(current: Image.Image, updated: Image.Image) -> Image.Image:
    if updated is not current:
        current.close()
    return updated


def _resize_logo(logo: Image.Image, photo: Image.Image) -> Image.Image:
    is_vertical = photo.height > photo.width

    if is_vertical:
        logo_width = max(1, int(photo.width * WATERMARK_WIDTH_RATIO_VERTICAL))
        ratio = logo_width / logo.width
        logo_height = max(1, int(logo.height * ratio))
    else:
        logo_height = max(1, int(photo.height * WATERMARK_HEIGHT_RATIO))
        ratio = logo_height / logo.height
        logo_width = max(1, int(logo.width * ratio))

    return logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)


def apply_watermark(source_path: Path, destination_path: Path) -> None:
    if not WATERMARK_PATH.is_file():
        raise WatermarkError(f"Watermark file not found: {WATERMARK_PATH}")

    photo: Image.Image | None = None
    logo: Image.Image | None = None

    try:
        with Image.open(source_path) as source:
            transposed = ImageOps.exif_transpose(source)
            photo = _detach_image(transposed, source)

        if photo.mode != "RGB":
            photo = _replace_image(photo, photo.convert("RGB"))

        with Image.open(WATERMARK_PATH) as logo_source:
            logo_rgba = logo_source.convert("RGBA")
            logo = _resize_logo(logo_rgba, photo)
            if logo is not logo_rgba:
                logo_rgba.close()

            position = (
                WATERMARK_MARGIN,
                photo.height - logo.height - WATERMARK_MARGIN,
            )
            photo.paste(logo, position, logo)

        photo.save(
            destination_path,
            "JPEG",
            quality=JPEG_QUALITY,
        )
    except WatermarkError:
        raise
    except Exception as exc:
        logger.exception("Failed to apply watermark to %s", source_path)
        raise WatermarkError("Failed to process image") from exc
    finally:
        if logo is not None:
            logo.close()
        if photo is not None:
            photo.close()
        release_memory()
