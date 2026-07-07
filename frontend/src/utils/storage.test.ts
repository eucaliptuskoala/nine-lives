/**
 * Unit tests for storage utilities
 * 
 * These tests validate file validation, path generation, and helper functions.
 * Note: Tests for actual upload/download operations require integration testing
 * with a real or mocked Supabase instance.
 */

import { describe, it, expect } from "vitest";
import { validateImageFile, formatFileSize } from "./storage";

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
