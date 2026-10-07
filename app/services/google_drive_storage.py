"""Small authenticated client for the project's Google Apps Script Drive gateway."""

import base64
import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
_DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,200}$")
_SCRIPT_URL = re.compile(r"^https://script\.google\.com/macros/s/[^/]+/exec$")


class GoogleDriveStorageError(ValueError):
    pass


def validate_settings(web_app_url, shared_secret):
    return bool(
        web_app_url
        and _SCRIPT_URL.fullmatch(web_app_url.strip())
        and shared_secret
        and len(shared_secret) >= 32
    )


def _call(web_app_url, shared_secret, action, **fields):
    if not validate_settings(web_app_url, shared_secret):
        raise GoogleDriveStorageError("Google Drive storage is not configured correctly.")
    payload = {"secret": shared_secret, "action": action, **fields}
    request = Request(
        web_app_url.strip(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read(1024 * 1024).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("Google Drive Apps Script request failed (%s).", type(error).__name__)
        raise GoogleDriveStorageError("Google Drive could not process this image. Try again later.") from error
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise GoogleDriveStorageError("Google Drive rejected the image request. Check the Apps Script setup.")
    return result


def upload_image(web_app_url, shared_secret, filename, image_bytes):
    response = _call(
        web_app_url,
        shared_secret,
        "upload",
        fileName=filename,
        mimeType="image/webp",
        base64=base64.b64encode(image_bytes).decode("ascii"),
    )
    file_id = response.get("fileId", "")
    if not isinstance(file_id, str) or not _DRIVE_ID.fullmatch(file_id):
        raise GoogleDriveStorageError("Google Drive returned an invalid file reference.")
    return file_id


def delete_image(web_app_url, shared_secret, file_id):
    if not isinstance(file_id, str) or not _DRIVE_ID.fullmatch(file_id):
        return False
    try:
        return _call(web_app_url, shared_secret, "delete", fileId=file_id).get("deleted") is True
    except GoogleDriveStorageError:
        logger.warning("Could not delete Drive image %s; it may need manual cleanup.", file_id)
        return False


def drive_image_url(file_id):
    if not isinstance(file_id, str) or not _DRIVE_ID.fullmatch(file_id):
        raise ValueError("Invalid Google Drive image ID.")
    return "https://drive.google.com/thumbnail?" + urlencode({"id": file_id, "sz": "w1600"})


def image_file_id(image_path):
    if not isinstance(image_path, str) or not image_path.startswith("gdrive:"):
        return None
    file_id = image_path.removeprefix("gdrive:")
    return file_id if _DRIVE_ID.fullmatch(file_id) else None
