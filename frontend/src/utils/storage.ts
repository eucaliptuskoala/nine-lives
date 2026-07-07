/**
 * Cat Image Utilities
 *
 * Client-side helpers for validating and describing cat photo uploads. Actual
 * storage writes go through the backend (`POST /api/digitize`, see
 * `api/digitize.ts`) — this module intentionally does NOT talk to Supabase
 * Storage directly, keeping the backend authoritative over all image
 * persistence (uploads and deletes alike require ownership checks that only
 * the backend performs).
 *
 * Related: Requirements 1.1, 1.2, 5.2, 26.1
 */

// Constants
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB in bytes
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
 * Validate a file before upload
 * 
 * Checks:
 * - File type (MIME type and extension)
 * - File size (max 10MB)
 * 
 * @param file - The file to validate
 * @returns Validation result with error message if invalid
 */
export function validateImageFile(file: File): FileValidationResult {
  // Check MIME type
  if (!ALLOWED_MIME_TYPES.includes(file.type)) {
    return {
      valid: false,
      error: "Invalid file type. Please upload a JPEG, PNG, or WebP image.",
    };
  }

  // Check file extension
  const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return {
      valid: false,
      error: "Invalid file extension. Please use .jpg, .jpeg, .png, or .webp.",
    };
  }

  // Check file size
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
 * Format file size in human-readable format
 * 
 * @param bytes - File size in bytes
 * @returns Formatted string (e.g., "2.5 MB")
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}
