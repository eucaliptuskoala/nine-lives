/**
 * Supabase Storage Utilities for Cat Images
 * 
 * This module provides helper functions for uploading, downloading, and managing
 * cat images in the Supabase storage bucket.
 * 
 * Related: Requirements 1.1, 1.2, 5.2, 26.1
 */

import { supabase } from "../hooks/useSupabase";

// Constants
const BUCKET_NAME = "cat-images";
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
 * Result of a file upload operation
 */
export interface UploadResult {
  success: boolean;
  url?: string;
  error?: string;
  path?: string;
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
 * Generate a unique file path for a user's uploaded cat photo
 * 
 * Format: {user_id}/source-{timestamp}.{extension}
 * 
 * @param userId - The user's ID
 * @param fileName - Original file name
 * @returns Storage path
 */
let lastSourceTimestamp = 0;

export function generateSourceImagePath(
  userId: string,
  fileName: string
): string {
  // Use a strictly-increasing timestamp so multiple calls within the same
  // millisecond still produce unique paths (the storage upload uses
  // `upsert: false`, so a collision would otherwise fail the second upload).
  let timestamp = Date.now();
  if (timestamp <= lastSourceTimestamp) {
    timestamp = lastSourceTimestamp + 1;
  }
  lastSourceTimestamp = timestamp;

  const extension = fileName.split(".").pop()?.toLowerCase();
  return `${userId}/source-${timestamp}.${extension}`;
}

/**
 * Generate a file path for an AI-generated cat avatar
 * 
 * Format: {user_id}/avatar-{cat_id}.png
 * 
 * @param userId - The user's ID
 * @param catId - The cat's ID
 * @returns Storage path
 */
export function generateAvatarPath(userId: string, catId: string): string {
  return `${userId}/avatar-${catId}.png`;
}

/**
 * Upload a cat photo to Supabase storage
 * 
 * The file will be validated before upload. The user must be authenticated.
 * 
 * @param file - The image file to upload
 * @param userId - The user's ID (for folder organization)
 * @returns Upload result with public URL if successful
 */
export async function uploadCatPhoto(
  file: File,
  userId: string
): Promise<UploadResult> {
  // Validate file
  const validation = validateImageFile(file);
  if (!validation.valid) {
    return {
      success: false,
      error: validation.error,
    };
  }

  try {
    // Generate unique file path
    const filePath = generateSourceImagePath(userId, file.name);

    // Upload to storage
    const { error } = await supabase.storage
      .from(BUCKET_NAME)
      .upload(filePath, file, {
        cacheControl: "3600",
        upsert: false, // Don't overwrite existing files
      });

    if (error) {
      throw error;
    }

    // Get public URL
    const {
      data: { publicUrl },
    } = supabase.storage.from(BUCKET_NAME).getPublicUrl(filePath);

    return {
      success: true,
      url: publicUrl,
      path: filePath,
    };
  } catch (error) {
    console.error("Upload error:", error);
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Upload failed. Please try again.",
    };
  }
}

/**
 * Get the public URL for a file in storage
 * 
 * Note: This doesn't check if the file exists, it just constructs the URL.
 * 
 * @param filePath - The file path in storage (e.g., "user_id/source-123.jpg")
 * @returns Public URL
 */
export function getPublicUrl(filePath: string): string {
  const {
    data: { publicUrl },
  } = supabase.storage.from(BUCKET_NAME).getPublicUrl(filePath);
  return publicUrl;
}

/**
 * Delete a file from storage
 * 
 * The user must own the file (RLS will enforce this).
 * 
 * @param filePath - The file path to delete
 * @returns True if successful
 */
export async function deleteFile(filePath: string): Promise<boolean> {
  try {
    const { error } = await supabase.storage
      .from(BUCKET_NAME)
      .remove([filePath]);

    if (error) {
      throw error;
    }

    return true;
  } catch (error) {
    console.error("Delete error:", error);
    return false;
  }
}

/**
 * Delete all images associated with a cat
 * 
 * This will attempt to delete both the source image and avatar.
 * 
 * @param userId - The user's ID
 * @param catId - The cat's ID
 * @returns Number of files successfully deleted
 */
export async function deleteCatImages(
  userId: string,
  catId: string
): Promise<number> {
  let deletedCount = 0;

  try {
    // List all files in user's folder
    const { data: files, error: listError } = await supabase.storage
      .from(BUCKET_NAME)
      .list(userId);

    if (listError || !files) {
      console.error("List error:", listError);
      return 0;
    }

    // Find files related to this cat
    const catFiles = files.filter(
      (file) =>
        file.name.includes(catId) ||
        file.name.startsWith(`source-`) ||
        file.name.startsWith(`avatar-${catId}`)
    );

    // Delete each file
    for (const file of catFiles) {
      const filePath = `${userId}/${file.name}`;
      const success = await deleteFile(filePath);
      if (success) {
        deletedCount++;
      }
    }

    return deletedCount;
  } catch (error) {
    console.error("Delete cat images error:", error);
    return deletedCount;
  }
}

/**
 * Check if a file exists in storage
 * 
 * @param filePath - The file path to check
 * @returns True if file exists
 */
export async function fileExists(filePath: string): Promise<boolean> {
  try {
    const { data, error } = await supabase.storage
      .from(BUCKET_NAME)
      .list(filePath.split("/")[0]);

    if (error || !data) {
      return false;
    }

    const fileName = filePath.split("/").pop();
    return data.some((file) => file.name === fileName);
  } catch (error) {
    console.error("File exists check error:", error);
    return false;
  }
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

/**
 * Extract file extension from file name
 * 
 * @param fileName - The file name
 * @returns File extension (lowercase, without dot)
 */
export function getFileExtension(fileName: string): string {
  if (!fileName.includes(".")) return "";
  return fileName.split(".").pop()?.toLowerCase() || "";
}

/**
 * Check if a file is an image based on MIME type
 * 
 * @param mimeType - The MIME type to check
 * @returns True if image
 */
export function isImageMimeType(mimeType: string): boolean {
  return ALLOWED_MIME_TYPES.includes(mimeType);
}

/**
 * Storage bucket constants for external use
 */
export const STORAGE_CONSTANTS = {
  BUCKET_NAME,
  MAX_FILE_SIZE,
  MAX_FILE_SIZE_MB: MAX_FILE_SIZE / (1024 * 1024),
  ALLOWED_MIME_TYPES,
  ALLOWED_EXTENSIONS,
} as const;
