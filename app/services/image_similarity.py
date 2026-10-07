from pathlib import Path

from PIL import Image, ImageOps


HASH_SIZE = 8


def _average_hash(image_path):
    with Image.open(image_path) as image:
        image = ImageOps.exif_transpose(image).convert("L").resize((HASH_SIZE, HASH_SIZE), Image.Resampling.LANCZOS)
        pixels = list(image.getdata())
    average = sum(pixels) / len(pixels)
    return tuple(pixel >= average for pixel in pixels)


def image_similarity(first_path, second_path):
    """Return a basic perceptual-hash similarity percentage, or None if unavailable."""
    if not first_path or not second_path:
        return None
    try:
        first_hash = _average_hash(Path(first_path))
        second_hash = _average_hash(Path(second_path))
    except (OSError, ValueError):
        return None
    distance = sum(first != second for first, second in zip(first_hash, second_hash))
    return round((1 - distance / len(first_hash)) * 100, 1)
