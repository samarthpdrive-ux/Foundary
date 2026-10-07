import logging
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.google_drive_storage import delete_image, image_file_id, upload_image


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_SIDE = 6000
UPLOAD_IMAGE_SIDE = 1440


logger = logging.getLogger(__name__)


def image_storage_options(config):
    if config.get("IMAGE_STORAGE_BACKEND", "local") == "google_drive":
        return {
            "drive_url": config.get("GOOGLE_DRIVE_WEB_APP_URL", ""),
            "drive_secret": config.get("GOOGLE_DRIVE_SHARED_SECRET", ""),
        }
    return {}


def save_item_image(file_storage, upload_dir, *, drive_url="", drive_secret=""):
    if not file_storage or not file_storage.filename:
        return None

    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    try:
        extension = Path(file_storage.filename).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("Use a .jpg, .jpeg, .png, or .webp image file.")
        image = Image.open(file_storage.stream)
        if image.format not in ALLOWED_FORMATS:
            raise ValueError("Upload a JPEG, PNG, or WebP image.")
        expected_formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
        if image.format != expected_formats[extension]:
            raise ValueError("The file extension does not match the image format.")
        if image.width > MAX_IMAGE_SIDE or image.height > MAX_IMAGE_SIDE or image.width * image.height > 36_000_000:
            raise ValueError("The image dimensions are too large. Choose an image up to 6000 × 6000 pixels.")
        image.verify()
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((UPLOAD_IMAGE_SIDE, UPLOAD_IMAGE_SIDE), Image.Resampling.BILINEAR)
        optimized = BytesIO()
        image.save(optimized, "WEBP", quality=80, method=3)
        image_bytes = optimized.getvalue()
        filename = f"{uuid4().hex}.webp"
        if drive_url or drive_secret:
            file_id = upload_image(drive_url, drive_secret, filename, image_bytes)
            try:
                (upload_dir / f"{file_id}.webp").write_bytes(image_bytes)
            except OSError:
                logger.info("Drive image cache could not be written; remote image remains available.")
            return f"gdrive:{file_id}"
        (upload_dir / filename).write_bytes(image_bytes)
        return filename
    except UnidentifiedImageError as error:
        raise ValueError("The uploaded file is not a valid image.") from error
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("The image file could not be processed. Choose a valid, smaller image.") from error


def remove_item_image(filename, upload_dir, *, drive_url="", drive_secret=""):
    if not filename:
        return
    upload_dir = Path(upload_dir)
    file_id = image_file_id(filename)
    if file_id:
        delete_image(drive_url, drive_secret, file_id)
        path = upload_dir / f"{file_id}.webp"
    else:
        path = upload_dir / Path(filename).name
    if path.is_file():
        path.unlink()


def local_image_path(image_path, upload_dir):
    """Return a local image/cache path without doing network I/O in a request."""
    upload_dir = Path(upload_dir)
    file_id = image_file_id(image_path)
    path = upload_dir / (f"{file_id}.webp" if file_id else Path(image_path or "").name)
    return path if path.is_file() else None
