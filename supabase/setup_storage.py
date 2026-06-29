#!/usr/bin/env python3
"""
Storage Bucket Setup Script for Nine Lives

This script programmatically creates and configures the cat-images storage bucket
using the Supabase Python client.

Requirements:
    pip install supabase

Usage:
    python setup_storage.py

Environment Variables:
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_KEY - Your Supabase service role key (keep secret!)
"""

import os
import sys
from typing import Dict, Any

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not found.")
    print("Please install it with: pip install supabase")
    sys.exit(1)


def get_supabase_client() -> Client:
    """Create authenticated Supabase client using service key."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: Missing environment variables")
        print("Please set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        sys.exit(1)
    
    return create_client(supabase_url, supabase_key)


def create_storage_bucket(client: Client) -> bool:
    """
    Create the cat-images storage bucket with proper configuration.
    
    Returns:
        True if successful, False otherwise
    """
    bucket_config = {
        "id": "cat-images",
        "name": "cat-images",
        "public": True,  # Enable public read access
        "file_size_limit": 10485760,  # 10MB in bytes
        "allowed_mime_types": [
            "image/jpeg",
            "image/png",
            "image/webp"
        ]
    }
    
    try:
        # Check if bucket already exists
        buckets = client.storage.list_buckets()
        bucket_exists = any(b["id"] == "cat-images" for b in buckets)
        
        if bucket_exists:
            print("✓ Bucket 'cat-images' already exists")
            
            # Update bucket configuration
            print("  Updating bucket configuration...")
            client.storage.update_bucket(
                "cat-images",
                {
                    "public": bucket_config["public"],
                    "file_size_limit": bucket_config["file_size_limit"],
                    "allowed_mime_types": bucket_config["allowed_mime_types"]
                }
            )
            print("✓ Bucket configuration updated")
        else:
            # Create new bucket
            print("Creating bucket 'cat-images'...")
            client.storage.create_bucket(
                "cat-images",
                {
                    "public": bucket_config["public"],
                    "file_size_limit": bucket_config["file_size_limit"],
                    "allowed_mime_types": bucket_config["allowed_mime_types"]
                }
            )
            print("✓ Bucket 'cat-images' created successfully")
        
        return True
    
    except Exception as e:
        print(f"✗ Error managing bucket: {e}")
        return False


def verify_bucket_config(client: Client) -> bool:
    """
    Verify the bucket configuration is correct.
    
    Returns:
        True if configuration matches expected values
    """
    try:
        buckets = client.storage.list_buckets()
        bucket = next((b for b in buckets if b["id"] == "cat-images"), None)
        
        if not bucket:
            print("✗ Bucket 'cat-images' not found")
            return False
        
        print("\nBucket Configuration:")
        print(f"  ID: {bucket.get('id')}")
        print(f"  Name: {bucket.get('name')}")
        print(f"  Public: {bucket.get('public')}")
        print(f"  File Size Limit: {bucket.get('file_size_limit')} bytes")
        print(f"  Allowed MIME Types: {bucket.get('allowed_mime_types')}")
        
        # Verify settings
        checks = {
            "Public access enabled": bucket.get("public") == True,
            "File size limit correct": bucket.get("file_size_limit") == 10485760,
            "MIME types configured": bucket.get("allowed_mime_types") is not None
        }
        
        print("\nConfiguration Checks:")
        all_passed = True
        for check, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"✗ Error verifying bucket: {e}")
        return False


def print_next_steps():
    """Print instructions for next steps."""
    print("\n" + "="*60)
    print("Next Steps:")
    print("="*60)
    print("\n1. Run the SQL script to create RLS policies:")
    print("   - Open Supabase Dashboard → SQL Editor")
    print("   - Copy contents of 'storage_setup.sql'")
    print("   - Execute the script")
    print("\n2. Test the storage bucket:")
    print("   - Upload a cat photo from the Digitize Page")
    print("   - Verify the image appears in Storage dashboard")
    print("   - Check that public URL works without authentication")
    print("\n3. Review documentation:")
    print("   - See STORAGE_BUCKET_DOCUMENTATION.md for details")
    print("   - Check README.md for troubleshooting")
    print("\n" + "="*60)


def main():
    """Main setup function."""
    print("="*60)
    print("Nine Lives - Storage Bucket Setup")
    print("="*60)
    print()
    
    # Get Supabase client
    print("Connecting to Supabase...")
    client = get_supabase_client()
    print("✓ Connected successfully\n")
    
    # Create or update bucket
    if not create_storage_bucket(client):
        print("\n✗ Setup failed")
        sys.exit(1)
    
    # Verify configuration
    print("\nVerifying configuration...")
    if not verify_bucket_config(client):
        print("\n⚠ Warning: Configuration verification failed")
        print("Please review the settings manually in Supabase Dashboard")
    
    # Print next steps
    print_next_steps()
    
    print("✓ Storage bucket setup complete!")


if __name__ == "__main__":
    main()
