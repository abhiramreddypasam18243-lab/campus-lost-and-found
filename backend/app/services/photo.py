import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, ImageFilter

from app.domain.image_hash import compute_dhash

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB (AC-32)
MAX_DIMENSION = 6000  # 6,000 x 6,000 px guard (AC-32)
MAX_PROCESSED_SIDE = 1600  # Resized to at most 1,600 px long side (AC-33)
THUMBNAIL_SIDE = 256


@dataclass(frozen=True)
class ProcessedImage:
    storage_key: str
    thumbnail_key: str
    original_mime: str
    sha256: str
    dhash: str
    width: int
    height: int


def validate_image_file(content: bytes) -> tuple[str, str]:
    """AC-31 & AC-32: Validate file content type by magic bytes and guard pixel dimensions."""
    # 1. Size guard
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={"code": "image_too_large", "message": "Image size exceeds 5 MB limit."},
        )

    # 2. Magic byte inspection (AC-31)
    mime: str
    ext: str
    if content.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
        ext = ".jpg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
        ext = ".png"
    elif content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
        mime = "image/webp"
        ext = ".webp"
    else:
        # SVG, GIF, text, executable, etc.
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_media_type",
                "message": "Only JPEG, PNG, and WebP images are accepted.",
            },
        )

    # 3. Dimension guard before decoding raster (AC-32)
    try:
        with Image.open(BytesIO(content)) as img:
            w, h = img.size
            if w > MAX_DIMENSION or h > MAX_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={
                        "code": "image_too_large",
                        "message": f"Image dimensions {w}x{h} exceed 6,000x6,000 maximum.",
                    },
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": "corrupted_image", "message": "Failed to decode image."},
        ) from exc

    return mime, ext


def process_and_save_photo(
    content: bytes,
    upload_dir: str,
    privacy_regions: Sequence[tuple[int, int, int, int]] | None = None,
) -> ProcessedImage:
    """AC-33, AC-34, AC-37, Step 15: Strip EXIF, redact privacy zones, resize, thumbnail, compute dhash, and save."""
    mime, ext = validate_image_file(content)
    sha256 = hashlib.sha256(content).hexdigest()

    # Open image and remove EXIF metadata
    with Image.open(BytesIO(content)) as original_img:
        # Copy pixel data into a new Image instance without info/exif dict
        clean_img = Image.new(original_img.mode, original_img.size)
        clean_img.putdata(list(original_img.getdata()))  # Strips all metadata

        # Convert palette/RGBA modes if saving as JPEG
        save_format = "JPEG" if mime == "image/jpeg" else ("PNG" if mime == "image/png" else "WEBP")
        if save_format == "JPEG" and clean_img.mode in ("RGBA", "P"):
            clean_img = clean_img.convert("RGB")

        # Step 15 Privacy Blurring: Redact sensitive privacy zones (faces, plates)
        if privacy_regions:
            img_w, img_h = clean_img.size
            for x, y, rw, rh in privacy_regions:
                x1 = max(0, min(x, img_w))
                y1 = max(0, min(y, img_h))
                x2 = max(0, min(x + rw, img_w))
                y2 = max(0, min(y + rh, img_h))
                if x2 > x1 and y2 > y1:
                    box = (x1, y1, x2, y2)
                    region = clean_img.crop(box)
                    blurred = region.filter(ImageFilter.GaussianBlur(radius=15))
                    clean_img.paste(blurred, box)

        # Resize if long side > 1,600 px (AC-33)
        w, h = clean_img.size
        if max(w, h) > MAX_PROCESSED_SIDE:
            clean_img.thumbnail((MAX_PROCESSED_SIDE, MAX_PROCESSED_SIDE), Image.Resampling.LANCZOS)
            w, h = clean_img.size

        # Compute 64-bit dHash (AC-37)
        buffer = BytesIO()
        clean_img.save(buffer, format=save_format)
        processed_bytes = buffer.getvalue()
        dhash = compute_dhash(processed_bytes)

        # Generate random UUID storage keys (AC-34)
        random_id = uuid.uuid4().hex
        storage_key = f"{random_id}{ext}"
        thumbnail_key = f"thumb_{random_id}{ext}"

        # Ensure directory exists
        dest_dir = Path(upload_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Save main image
        clean_img.save(dest_dir / storage_key, format=save_format)

        # Create and save thumbnail (AC-33)
        thumb_img = clean_img.copy()
        thumb_img.thumbnail((THUMBNAIL_SIDE, THUMBNAIL_SIDE), Image.Resampling.LANCZOS)
        thumb_img.save(dest_dir / thumbnail_key, format=save_format)

        return ProcessedImage(
            storage_key=storage_key,
            thumbnail_key=thumbnail_key,
            original_mime=mime,
            sha256=sha256,
            dhash=dhash,
            width=w,
            height=h,
        )
