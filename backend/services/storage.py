"""
Supabase Storage Service for Cat Images

This module provides helper functions for uploading cat avatars to Supabase storage
from the backend. The backend uses the service key to bypass RLS policies.

Related: Requirements 5.2, 5.3
"""

import os
from typing import Optional
from supabase import create_client, Client


# Constants
BUCKET_NAME = "cat-images"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"]


def get_supabase_client() -> Client:
    """
    Create a Supabase client using service key.
    
    The service key bypasses RLS policies, allowing the backend to upload
    files to any user's folder.
    
    Returns:
        Authenticated Supabase client
        
    Raises:
        ValueError: If environment variables are not set
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables"
        )
    
    return create_client(supabase_url, supabase_key)


def generate_avatar_path(user_id: str, cat_id: str) -> str:
    """
    Generate storage path for a cat avatar.
    
    Format: {user_id}/avatar-{cat_id}.png
    
    Args:
        user_id: The user's ID
        cat_id: The cat's ID
        
    Returns:
        Storage path string
    """
    return f"{user_id}/avatar-{cat_id}.png"


async def upload_avatar(
    image_bytes: bytes,
    user_id: str,
    cat_id: str,
    content_type: str = "image/png"
) -> str:
    """
    Upload a generated cat avatar to Supabase storage.
    
    This function is typically called after generating an avatar with Gemini API.
    It uploads the image bytes to the user's folder in the cat-images bucket.
    
    Args:
        image_bytes: PNG/JPEG/WebP image data
        user_id: Owner's user ID (for folder organization)
        cat_id: Cat's unique ID (for file naming)
        content_type: MIME type of the image (default: image/png)
        
    Returns:
        Public URL of the uploaded avatar
        
    Raises:
        ValueError: If content_type is not allowed
        Exception: If upload fails
    """
    # Validate content type
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Invalid content type: {content_type}. "
            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Validate file size
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / (1024 * 1024)
        raise ValueError(
            f"File too large: {size_mb:.2f}MB. Maximum size is 10MB."
        )
    
    # Get Supabase client
    client = get_supabase_client()
    
    # Generate file path
    file_path = generate_avatar_path(user_id, cat_id)
    
    try:
        # Upload to storage
        result = client.storage.from_(BUCKET_NAME).upload(
            file_path,
            image_bytes,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "true"  # Overwrite if exists
            }
        )
        
        if hasattr(result, 'error') and result.error:
            raise Exception(f"Upload failed: {result.error}")
        
        # Get public URL
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        
        return public_url
    
    except Exception as e:
        raise Exception(f"Failed to upload avatar: {str(e)}")


async def upload_source_image(
    image_bytes: bytes,
    user_id: str,
    file_name: str,
    content_type: str
) -> str:
    """
    Upload a user's source cat photo to Supabase storage.
    
    This is typically called when the backend receives a cat photo upload.
    
    Args:
        image_bytes: Image data
        user_id: Owner's user ID
        file_name: Original file name (for extension)
        content_type: MIME type of the image
        
    Returns:
        Public URL of the uploaded image
        
    Raises:
        ValueError: If content_type is not allowed
        Exception: If upload fails
    """
    # Validate content type
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Invalid content type: {content_type}. "
            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )
    
    # Validate file size
    if len(image_bytes) > MAX_FILE_SIZE:
        size_mb = len(image_bytes) / (1024 * 1024)
        raise ValueError(
            f"File too large: {size_mb:.2f}MB. Maximum size is 10MB."
        )
    
    # Get Supabase client
    client = get_supabase_client()
    
    # Generate unique file path
    import time
    timestamp = int(time.time() * 1000)
    extension = file_name.split(".")[-1].lower()
    file_path = f"{user_id}/source-{timestamp}.{extension}"
    
    try:
        # Upload to storage
        result = client.storage.from_(BUCKET_NAME).upload(
            file_path,
            image_bytes,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false"  # Don't overwrite
            }
        )
        
        if hasattr(result, 'error') and result.error:
            raise Exception(f"Upload failed: {result.error}")
        
        # Get public URL
        public_url = client.storage.from_(BUCKET_NAME).get_public_url(file_path)
        
        return public_url
    
    except Exception as e:
        raise Exception(f"Failed to upload source image: {str(e)}")


def get_public_url(file_path: str) -> str:
    """
    Get the public URL for a file in storage.
    
    Note: This doesn't check if the file exists, it just constructs the URL.
    
    Args:
        file_path: The file path in storage (e.g., "user_id/source-123.jpg")
        
    Returns:
        Public URL string
    """
    client = get_supabase_client()
    return client.storage.from_(BUCKET_NAME).get_public_url(file_path)


async def delete_file(file_path: str) -> bool:
    """
    Delete a file from storage.
    
    Args:
        file_path: The file path to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_supabase_client()
        result = client.storage.from_(BUCKET_NAME).remove([file_path])
        
        if hasattr(result, 'error') and result.error:
            return False
        
        return True
    
    except Exception as e:
        print(f"Delete error: {e}")
        return False


async def delete_cat_images(user_id: str, cat_id: str) -> int:
    """
    Delete all images associated with a cat.
    
    This will attempt to delete both the source image and avatar.
    
    Args:
        user_id: The user's ID
        cat_id: The cat's ID
        
    Returns:
        Number of files successfully deleted
    """
    deleted_count = 0
    
    try:
        client = get_supabase_client()
        
        # List all files in user's folder
        result = client.storage.from_(BUCKET_NAME).list(user_id)
        
        if hasattr(result, 'error') and result.error:
            return 0
        
        files = result if isinstance(result, list) else []
        
        # Find files related to this cat
        cat_files = [
            f for f in files
            if cat_id in f.get("name", "")
        ]
        
        # Delete each file
        for file in cat_files:
            file_path = f"{user_id}/{file['name']}"
            if await delete_file(file_path):
                deleted_count += 1
        
        return deleted_count
    
    except Exception as e:
        print(f"Delete cat images error: {e}")
        return deleted_count


def format_file_size(bytes_size: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        bytes_size: File size in bytes
        
    Returns:
        Formatted string (e.g., "2.5 MB")
    """
    if bytes_size == 0:
        return "0 Bytes"
    
    sizes = ["Bytes", "KB", "MB", "GB"]
    k = 1024
    i = 0
    
    size = float(bytes_size)
    while size >= k and i < len(sizes) - 1:
        size /= k
        i += 1
    
    return f"{size:.2f} {sizes[i]}"


# Export constants for external use
STORAGE_CONSTANTS = {
    "BUCKET_NAME": BUCKET_NAME,
    "MAX_FILE_SIZE": MAX_FILE_SIZE,
    "MAX_FILE_SIZE_MB": MAX_FILE_SIZE / (1024 * 1024),
    "ALLOWED_MIME_TYPES": ALLOWED_MIME_TYPES,
}
