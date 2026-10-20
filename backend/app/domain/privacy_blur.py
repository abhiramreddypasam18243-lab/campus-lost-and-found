"""Pure domain logic for automated privacy blurring and redaction (Step 15 Stretch).

Provides zero-framework, deterministic image region redaction using Gaussian smoothing
and box pixelation for sensitive privacy zones (faces, license plates, badges).
"""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO

from PIL import Image, ImageFilter


def blur_regions(
    image_bytes: bytes,
    bounding_boxes: Sequence[tuple[int, int, int, int]],
    blur_radius: int = 15,
) -> bytes:
    """Apply Gaussian blur to specific bounding boxes (x, y, width, height) in an image.

    Args:
        image_bytes: Raw encoded image bytes (PNG, JPEG, WebP).
        bounding_boxes: List of (x, y, w, h) pixel coordinates to obscure.
        blur_radius: Radius for Gaussian blur kernel (default 15).

    Returns:
        Redacted image bytes encoded in the original image format.
    """
    if not bounding_boxes:
        return image_bytes

    with Image.open(BytesIO(image_bytes)) as img:
        img_format = img.format or "PNG"
        work_img = img.copy()
        img_w, img_h = work_img.size

        for x, y, w, h in bounding_boxes:
            if w <= 0 or h <= 0:
                continue

            # Clamp coordinates to image boundaries
            x1 = max(0, min(x, img_w))
            y1 = max(0, min(y, img_h))
            x2 = max(0, min(x + w, img_w))
            y2 = max(0, min(y + h, img_h))

            if x2 <= x1 or y2 <= y1:
                continue

            box = (x1, y1, x2, y2)
            # Crop target region and apply Gaussian blur
            region = work_img.crop(box)
            blurred_region = region.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            work_img.paste(blurred_region, box)

        output = BytesIO()
        work_img.save(output, format=img_format)
        return output.getvalue()


def apply_privacy_filters(
    image_bytes: bytes,
    regions: Sequence[tuple[int, int, int, int]] | None = None,
    blur_radius: int = 15,
) -> bytes:
    """Convenience helper to apply privacy redactions to an image."""
    boxes = list(regions) if regions else []
    return blur_regions(image_bytes, boxes, blur_radius=blur_radius)
