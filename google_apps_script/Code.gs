/**
 * Foundry image storage gateway.
 * Set DRIVE_FOLDER_ID and API_SECRET under Project Settings > Script properties.
 */
function doPost(event) {
  try {
    const input = JSON.parse(event.postData.contents || "{}");
    const props = PropertiesService.getScriptProperties();
    const expectedSecret = props.getProperty("API_SECRET") || "";
    if (!expectedSecret || !input.secret || !constantTimeEquals_(String(input.secret), expectedSecret)) {
      return json_({ ok: false, error: "unauthorized" });
    }

    const folderId = props.getProperty("DRIVE_FOLDER_ID") || "";
    if (!folderId) return json_({ ok: false, error: "storage_not_configured" });
    const folder = DriveApp.getFolderById(folderId);

    if (input.action === "upload") return upload_(folder, input);
    if (input.action === "delete") return delete_(folder, input);
    return json_({ ok: false, error: "unknown_action" });
  } catch (error) {
    console.error("Drive gateway request failed: " + error.message);
    return json_({ ok: false, error: "request_failed" });
  }
}

function upload_(folder, input) {
  if (input.mimeType !== "image/webp" ||
      typeof input.fileName !== "string" || !/^[a-f0-9]{32}\.webp$/.test(input.fileName) ||
      typeof input.base64 !== "string" || input.base64.length > 7 * 1024 * 1024) {
    return json_({ ok: false, error: "invalid_image" });
  }
  const bytes = Utilities.base64Decode(input.base64);
  if (!bytes.length || bytes.length > 5 * 1024 * 1024) {
    return json_({ ok: false, error: "image_too_large" });
  }
  const blob = Utilities.newBlob(bytes, "image/webp", input.fileName);
  const file = folder.createFile(blob);
  // Public view access is required because report images are displayed to all app visitors.
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return json_({ ok: true, fileId: file.getId() });
}

function delete_(folder, input) {
  if (typeof input.fileId !== "string" || !/^[A-Za-z0-9_-]{10,200}$/.test(input.fileId)) {
    return json_({ ok: false, error: "invalid_file_id" });
  }
  const file = DriveApp.getFileById(input.fileId);
  const parents = file.getParents();
  let belongsToConfiguredFolder = false;
  while (parents.hasNext()) {
    if (parents.next().getId() === folder.getId()) {
      belongsToConfiguredFolder = true;
      break;
    }
  }
  if (!belongsToConfiguredFolder) return json_({ ok: false, error: "file_outside_storage_folder" });
  file.setTrashed(true);
  return json_({ ok: true, deleted: true });
}

function constantTimeEquals_(first, second) {
  let difference = first.length ^ second.length;
  const length = Math.max(first.length, second.length);
  for (let index = 0; index < length; index++) {
    difference |= (first.charCodeAt(index) || 0) ^ (second.charCodeAt(index) || 0);
  }
  return difference === 0;
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
