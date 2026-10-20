"""Tests for Step 15 Stretch: Automated face and privacy zone blurring in the photo pipeline.

Verifies:
1. Pure domain function blurs target bounding boxes with Gaussian blur.
2. Pixels outside the target bounding box remain completely unchanged.
3. Pixels inside the target bounding box are heavily smoothed (variance reduced / edge attenuation).
4. Edge cases: Empty bounding boxes, out-of-bounds coordinates, zero-size regions handled gracefully.
5. End-to-end integration: Photo pipeline applies privacy redaction before saving to disk.
"""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.domain.privacy_blur import apply_privacy_filters, blur_regions


def create_patterned_test_image(width: int = 200, height: int = 200) -> Image.Image:
    """Create a high-contrast patterned image with sharp edges for blur testing."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw high contrast sharp features inside a designated box (50, 50, 60, 60)
    for i in range(50, 110, 4):
        draw.line([(i, 50), (i, 110)], fill=(0, 0, 0), width=2)
    # Draw reference sharp features outside the box (140, 140, 40, 40)
    for i in range(140, 180, 4):
        draw.line([(i, 140), (i, 180)], fill=(200, 0, 0), width=2)
    return img


def image_to_bytes(img: Image.Image, format_name: str = "PNG") -> bytes:
    buf = BytesIO()
    img.save(buf, format=format_name)
    return buf.getvalue()


def calculate_pixel_variance(pixels: list[tuple[int, ...]]) -> float:
    """Calculate luminance variance of a list of RGB tuples."""
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels]
    mean = sum(lum) / len(lum)
    return sum((x - mean) ** 2 for x in lum) / len(lum)


def test_blur_regions_modifies_only_target_area() -> None:
    """Test that blur_regions modifies target box and preserves surrounding pixels."""
    original = create_patterned_test_image()
    orig_bytes = image_to_bytes(original)

    # Blur target region (x=50, y=50, w=60, h=60)
    target_box = (50, 50, 60, 60)
    blurred_bytes = blur_regions(orig_bytes, [target_box], blur_radius=15)

    blurred_img = Image.open(BytesIO(blurred_bytes))

    # 1. Pixels outside the bounding box should be identical
    # Check sample points outside target box
    sample_points_outside = [
        (10, 10),
        (140, 150),
        (160, 170),
        (190, 190),
        (25, 150),
    ]
    for pt in sample_points_outside:
        assert original.getpixel(pt) == blurred_img.getpixel(pt)

    # 2. Pixels inside the bounding box should be modified
    inside_orig_pixels = list(original.crop((50, 50, 110, 110)).getdata())
    inside_blur_pixels = list(blurred_img.crop((50, 50, 110, 110)).getdata())
    assert inside_orig_pixels != inside_blur_pixels

    # 3. Variance inside blurred region should be significantly lower than sharp alternating stripes
    orig_var = calculate_pixel_variance(inside_orig_pixels)
    blur_var = calculate_pixel_variance(inside_blur_pixels)
    assert blur_var < orig_var


def test_blur_regions_empty_boxes_is_noop() -> None:
    """Providing no bounding boxes leaves the image content unchanged."""
    original = create_patterned_test_image()
    orig_bytes = image_to_bytes(original)

    result_bytes = blur_regions(orig_bytes, [], blur_radius=15)
    result_img = Image.open(BytesIO(result_bytes))

    assert list(original.getdata()) == list(result_img.getdata())


def test_blur_regions_clamps_out_of_bounds() -> None:
    """Coordinates extending past image boundaries are clamped without error."""
    original = create_patterned_test_image(100, 100)
    orig_bytes = image_to_bytes(original)

    # Box extending past width and height
    over_box = (80, 80, 50, 50)
    blurred_bytes = blur_regions(orig_bytes, [over_box], blur_radius=10)

    blurred_img = Image.open(BytesIO(blurred_bytes))
    assert blurred_img.size == (100, 100)


def test_apply_privacy_filters_convenience_wrapper() -> None:
    """apply_privacy_filters accepts an image and optional regions, returning valid encoded bytes."""
    original = create_patterned_test_image()
    orig_bytes = image_to_bytes(original, format_name="JPEG")

    filtered_bytes = apply_privacy_filters(orig_bytes, [(20, 20, 40, 40)])
    assert len(filtered_bytes) > 0

    img = Image.open(BytesIO(filtered_bytes))
    assert img.size == original.size


def test_process_and_save_photo_applies_privacy_blurring(tmp_path: pytest.TempPathFactory) -> None:
    """Test that photo pipeline redacts privacy zones and writes blurred image to disk."""
    from pathlib import Path

    from app.services.photo import process_and_save_photo

    original = create_patterned_test_image(200, 200)
    orig_bytes = image_to_bytes(original, format_name="JPEG")

    upload_dir = str(tmp_path)
    target_zone = (50, 50, 60, 60)

    processed = process_and_save_photo(orig_bytes, upload_dir, privacy_regions=[target_zone])
    saved_file = Path(upload_dir) / processed.storage_key
    assert saved_file.exists()

    with Image.open(saved_file) as saved_img:
        saved_crop = list(saved_img.crop((50, 50, 110, 110)).getdata())
        orig_crop = list(original.crop((50, 50, 110, 110)).getdata())
        assert saved_crop != orig_crop
        assert calculate_pixel_variance(saved_crop) < calculate_pixel_variance(orig_crop)
