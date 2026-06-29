/**
 * Unit tests for storage utilities
 * 
 * These tests validate file validation, path generation, and helper functions.
 * Note: Tests for actual upload/download operations require integration testing
 * with a real or mocked Supabase instance.
 */

import { describe, it, expect } from "vitest";
import {
  validateImageFile,
  generateSourceImagePath,
  generateAvatarPath,
  formatFileSize,
  getFileExtension,
  isImageMimeType,
  STORAGE_CONSTANTS,
} from "./storage";

describe("validateImageFile", () => {
  it("should accept valid JPEG file", () => {
    const file = new File(["content"], "cat.jpg", { type: "image/jpeg" });
    Object.defineProperty(file, "size", { value: 1024 * 1024 }); // 1MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it("should accept valid PNG file", () => {
    const file = new File(["content"], "cat.png", { type: "image/png" });
    Object.defineProperty(file, "size", { value: 1024 * 1024 }); // 1MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it("should accept valid WebP file", () => {
    const file = new File(["content"], "cat.webp", { type: "image/webp" });
    Object.defineProperty(file, "size", { value: 1024 * 1024 }); // 1MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it("should reject file with invalid MIME type", () => {
    const file = new File(["content"], "cat.gif", { type: "image/gif" });
    Object.defineProperty(file, "size", { value: 1024 * 1024 }); // 1MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("Invalid file type");
  });

  it("should reject file that exceeds 10MB", () => {
    const file = new File(["content"], "cat.jpg", { type: "image/jpeg" });
    Object.defineProperty(file, "size", { value: 11 * 1024 * 1024 }); // 11MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("File too large");
  });

  it("should accept file at exactly 10MB", () => {
    const file = new File(["content"], "cat.jpg", { type: "image/jpeg" });
    Object.defineProperty(file, "size", { value: 10 * 1024 * 1024 }); // 10MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(true);
  });

  it("should reject file with invalid extension", () => {
    const file = new File(["content"], "cat.gif", { type: "image/jpeg" });
    Object.defineProperty(file, "size", { value: 1024 * 1024 }); // 1MB
    
    const result = validateImageFile(file);
    expect(result.valid).toBe(false);
    expect(result.error).toContain("Invalid file extension");
  });
});

describe("generateSourceImagePath", () => {
  it("should generate path with user ID and timestamp", () => {
    const userId = "user-123";
    const fileName = "my-cat.jpg";
    
    const path = generateSourceImagePath(userId, fileName);
    
    expect(path).toMatch(/^user-123\/source-\d+\.jpg$/);
  });

  it("should preserve file extension", () => {
    const userId = "user-456";
    
    const jpgPath = generateSourceImagePath(userId, "cat.jpg");
    expect(jpgPath).toMatch(/\.jpg$/);
    
    const pngPath = generateSourceImagePath(userId, "cat.png");
    expect(pngPath).toMatch(/\.png$/);
    
    const webpPath = generateSourceImagePath(userId, "cat.webp");
    expect(webpPath).toMatch(/\.webp$/);
  });

  it("should convert extension to lowercase", () => {
    const userId = "user-789";
    const fileName = "cat.JPG";
    
    const path = generateSourceImagePath(userId, fileName);
    
    expect(path).toMatch(/\.jpg$/);
    expect(path).not.toMatch(/\.JPG$/);
  });

  it("should generate unique paths for multiple calls", () => {
    const userId = "user-123";
    const fileName = "cat.jpg";
    
    const path1 = generateSourceImagePath(userId, fileName);
    const path2 = generateSourceImagePath(userId, fileName);
    
    expect(path1).not.toBe(path2);
  });
});

describe("generateAvatarPath", () => {
  it("should generate path with user ID and cat ID", () => {
    const userId = "user-123";
    const catId = "cat-456";
    
    const path = generateAvatarPath(userId, catId);
    
    expect(path).toBe("user-123/avatar-cat-456.png");
  });

  it("should always use .png extension", () => {
    const userId = "user-123";
    const catId = "cat-456";
    
    const path = generateAvatarPath(userId, catId);
    
    expect(path).toMatch(/\.png$/);
  });

  it("should be deterministic for same inputs", () => {
    const userId = "user-123";
    const catId = "cat-456";
    
    const path1 = generateAvatarPath(userId, catId);
    const path2 = generateAvatarPath(userId, catId);
    
    expect(path1).toBe(path2);
  });
});

describe("formatFileSize", () => {
  it("should format bytes correctly", () => {
    expect(formatFileSize(0)).toBe("0 Bytes");
    expect(formatFileSize(500)).toBe("500 Bytes");
    expect(formatFileSize(1023)).toBe("1023 Bytes");
  });

  it("should format kilobytes correctly", () => {
    expect(formatFileSize(1024)).toBe("1 KB");
    expect(formatFileSize(1536)).toBe("1.5 KB");
    expect(formatFileSize(10240)).toBe("10 KB");
  });

  it("should format megabytes correctly", () => {
    expect(formatFileSize(1024 * 1024)).toBe("1 MB");
    expect(formatFileSize(2.5 * 1024 * 1024)).toBe("2.5 MB");
    expect(formatFileSize(10 * 1024 * 1024)).toBe("10 MB");
  });

  it("should format gigabytes correctly", () => {
    expect(formatFileSize(1024 * 1024 * 1024)).toBe("1 GB");
    expect(formatFileSize(2.5 * 1024 * 1024 * 1024)).toBe("2.5 GB");
  });
});

describe("getFileExtension", () => {
  it("should extract extension from file name", () => {
    expect(getFileExtension("cat.jpg")).toBe("jpg");
    expect(getFileExtension("photo.png")).toBe("png");
    expect(getFileExtension("image.webp")).toBe("webp");
  });

  it("should return lowercase extension", () => {
    expect(getFileExtension("cat.JPG")).toBe("jpg");
    expect(getFileExtension("photo.PNG")).toBe("png");
  });

  it("should handle files with multiple dots", () => {
    expect(getFileExtension("my.cat.photo.jpg")).toBe("jpg");
  });

  it("should return empty string for files without extension", () => {
    expect(getFileExtension("noextension")).toBe("");
  });
});

describe("isImageMimeType", () => {
  it("should return true for allowed MIME types", () => {
    expect(isImageMimeType("image/jpeg")).toBe(true);
    expect(isImageMimeType("image/png")).toBe(true);
    expect(isImageMimeType("image/webp")).toBe(true);
  });

  it("should return false for disallowed MIME types", () => {
    expect(isImageMimeType("image/gif")).toBe(false);
    expect(isImageMimeType("image/svg+xml")).toBe(false);
    expect(isImageMimeType("application/pdf")).toBe(false);
    expect(isImageMimeType("text/plain")).toBe(false);
  });
});

describe("STORAGE_CONSTANTS", () => {
  it("should have correct bucket name", () => {
    expect(STORAGE_CONSTANTS.BUCKET_NAME).toBe("cat-images");
  });

  it("should have correct max file size", () => {
    expect(STORAGE_CONSTANTS.MAX_FILE_SIZE).toBe(10 * 1024 * 1024);
    expect(STORAGE_CONSTANTS.MAX_FILE_SIZE_MB).toBe(10);
  });

  it("should have correct allowed MIME types", () => {
    expect(STORAGE_CONSTANTS.ALLOWED_MIME_TYPES).toEqual([
      "image/jpeg",
      "image/png",
      "image/webp",
    ]);
  });

  it("should have correct allowed extensions", () => {
    expect(STORAGE_CONSTANTS.ALLOWED_EXTENSIONS).toEqual([
      ".jpg",
      ".jpeg",
      ".png",
      ".webp",
    ]);
  });
});
