from io import BytesIO

from PIL import Image


def compute_dhash(image_bytes: bytes) -> str:
    """Compute 64-bit difference hash (dHash) for an image.

    1. Grayscale conversion.
    2. Resize to 9x8 pixels (9 columns, 8 rows).
    3. Compare adjacent pixels horizontally: 8 * 8 = 64 comparisons.
    4. Return 16-character hexadecimal string.
    """
    img = Image.open(BytesIO(image_bytes)).convert("L")
    # 9 width, 8 height
    resized = img.resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(resized.getdata())  # 72 pixels in row-major order

    difference = []
    for row in range(8):
        for col in range(8):
            pixel_left = pixels[row * 9 + col]
            pixel_right = pixels[row * 9 + col + 1]
            difference.append(pixel_left > pixel_right)

    # Convert 64 booleans to 64-bit integer
    decimal_value = 0
    for bit in difference:
        decimal_value = (decimal_value << 1) | int(bit)

    # 16-character hex string (zero-padded)
    return f"{decimal_value:016x}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two 16-character hex difference hashes."""
    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    xor_val = val1 ^ val2
    return bin(xor_val).count("1")
