/**
 * Cat Image Utilities — client-side helpers for validating and describing cat
 * photo uploads. Actual storage writes go through the backend.
 */

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

/**
 * Validation result for file uploads
 */
export interface FileValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validate a file before upload.
 */
export function validateImageFile(file: File): FileValidationResult {
  if (!ALLOWED_MIME_TYPES.includes(file.type)) {
    return {
      valid: false,
      error: "Invalid file type. Please upload a JPEG, PNG, or WebP image.",
    };
  }

  const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return {
      valid: false,
      error: "Invalid file extension. Please use .jpg, .jpeg, .png, or .webp.",
    };
  }

  if (file.size > MAX_FILE_SIZE) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    return {
      valid: false,
      error: `File too large (${sizeMB}MB). Maximum size is 10MB.`,
    };
  }

  return { valid: true };
}

/**
 * Format file size in human-readable format.
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}
