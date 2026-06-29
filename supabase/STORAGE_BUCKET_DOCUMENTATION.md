# Cat Images Storage Bucket Documentation

## Overview

The `cat-images` storage bucket is used to store all user-uploaded cat photos and AI-generated cat avatars. This document describes the bucket configuration, access patterns, security policies, and usage examples.

## Bucket Configuration

### Basic Settings

- **Bucket ID**: `cat-images`
- **Bucket Name**: `cat-images`
- **Public Access**: Enabled (read-only for public, write restricted to owners)
- **File Size Limit**: 10MB (10,485,760 bytes)
- **Allowed MIME Types**:
  - `image/jpeg`
  - `image/png`
  - `image/webp`

### Storage Structure

Files are organized by user ID to ensure isolation and easy access control:

```
cat-images/
├── {user_id_1}/
│   ├── source-{timestamp}.jpg    # Original uploaded cat photo
│   ├── avatar-{cat_id}.png       # AI-generated avatar
│   └── ...
├── {user_id_2}/
│   ├── source-{timestamp}.webp
│   └── ...
└── ...
```

## Row-Level Security (RLS) Policies

### Policy 1: Upload to Own Folder

**Name**: "Users can upload to their own folder"

**Operation**: INSERT

**Target**: Authenticated users

**Rule**: Users can only upload files to paths that start with their user ID:
- ✅ Allowed: `{user_id}/source-image.jpg`
- ❌ Denied: `{other_user_id}/source-image.jpg`

**Use Case**: When users upload cat photos during digitization

### Policy 2: Update Own Files

**Name**: "Users can update their own files"

**Operation**: UPDATE

**Target**: Authenticated users

**Rule**: Users can only update files in their own folder

**Use Case**: Rare - typically used for re-uploading or replacing images

### Policy 3: Delete Own Files

**Name**: "Users can delete their own files"

**Operation**: DELETE

**Target**: Authenticated users

**Rule**: Users can only delete files in their own folder

**Use Case**: Cleanup operations, removing old cat photos

### Policy 4: Public Read Access

**Name**: "Public read access for all images"

**Operation**: SELECT

**Target**: Public (including anonymous users)

**Rule**: Anyone can read (view) any image in the bucket

**Use Case**: 
- Displaying cat avatars in the battle UI
- Viewing memorial cat images
- Sharing cat cards (future feature)

## Access Patterns

### Pattern 1: Upload Source Cat Photo

**When**: User uploads a cat photo on the Digitize Page

**Flow**:
1. Frontend validates file type and size
2. Frontend calls Supabase storage API with authentication token
3. File is uploaded to path: `{user_id}/source-{timestamp}.{ext}`
4. URL is returned: `{supabase_url}/storage/v1/object/public/cat-images/{user_id}/source-{timestamp}.{ext}`
5. URL is stored in `cat.source_image_url` field

**Example Code** (Frontend):
```typescript
import { supabase } from './hooks/useSupabase';

async function uploadCatPhoto(file: File, userId: string): Promise<string> {
  const timestamp = Date.now();
  const fileExt = file.name.split('.').pop();
  const fileName = `source-${timestamp}.${fileExt}`;
  const filePath = `${userId}/${fileName}`;

  const { data, error } = await supabase.storage
    .from('cat-images')
    .upload(filePath, file);

  if (error) {
    throw new Error(`Upload failed: ${error.message}`);
  }

  // Get public URL
  const { data: urlData } = supabase.storage
    .from('cat-images')
    .getPublicUrl(filePath);

  return urlData.publicUrl;
}
```

### Pattern 2: Upload Generated Avatar

**When**: Backend generates cat avatar using Gemini 2.5 Flash

**Flow**:
1. Backend receives generated avatar image bytes from Gemini API
2. Backend calls Supabase storage API with service key (bypasses RLS)
3. File is uploaded to path: `{user_id}/avatar-{cat_id}.png`
4. Public URL is returned and stored in `cat.avatar_url` field

**Example Code** (Backend):
```python
from supabase import create_client
import os

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(supabase_url, supabase_key)

async def upload_avatar(image_bytes: bytes, user_id: str, cat_id: str) -> str:
    """
    Upload generated cat avatar to Supabase storage.
    
    Args:
        image_bytes: PNG image data from Gemini API
        user_id: Owner's user ID
        cat_id: Cat's unique ID
    
    Returns:
        Public URL of uploaded avatar
    """
    file_path = f"{user_id}/avatar-{cat_id}.png"
    
    # Upload using service key (bypasses RLS for backend operations)
    result = supabase.storage.from_("cat-images").upload(
        file_path,
        image_bytes,
        file_options={"content-type": "image/png"}
    )
    
    if result.error:
        raise Exception(f"Avatar upload failed: {result.error}")
    
    # Get public URL
    public_url = supabase.storage.from_("cat-images").get_public_url(file_path)
    
    return public_url
```

### Pattern 3: Display Images in UI

**When**: Displaying cat cards, avatars, or memorial images

**Flow**:
1. Frontend loads cat data from database
2. `cat.avatar_url` and `cat.source_image_url` contain public URLs
3. URLs are used directly in `<img>` tags - no authentication required
4. Images are cached by browser

**Example Code** (Frontend):
```typescript
interface CatCardProps {
  cat: Cat;
}

function CatCard({ cat }: CatCardProps) {
  return (
    <div className="cat-card">
      <img 
        src={cat.avatar_url} 
        alt={`${cat.name} avatar`}
        className="cat-avatar"
      />
      {/* Cat stats and info */}
    </div>
  );
}
```

### Pattern 4: Delete Old Images (Cleanup)

**When**: User deletes a cat or performs cleanup

**Flow**:
1. Frontend calls delete API with authentication
2. Files are removed from user's folder
3. Database records are updated to reflect deletion

**Example Code** (Frontend):
```typescript
async function deleteCatImages(userId: string, catId: string): Promise<void> {
  const filesToDelete = [
    `${userId}/source-${catId}.jpg`,
    `${userId}/avatar-${catId}.png`
  ];

  const { error } = await supabase.storage
    .from('cat-images')
    .remove(filesToDelete);

  if (error) {
    throw new Error(`Delete failed: ${error.message}`);
  }
}
```

## File Naming Conventions

### Source Images (User Uploads)
- Format: `source-{timestamp}.{ext}`
- Example: `source-1704123456789.jpg`
- Rationale: Timestamp ensures uniqueness, easy sorting by upload time

### Avatar Images (AI Generated)
- Format: `avatar-{cat_id}.png`
- Example: `avatar-550e8400-e29b-41d4-a716-446655440000.png`
- Rationale: Cat ID ensures 1:1 mapping, easy lookup

## Validation and Error Handling

### Frontend Validation

Before upload, validate:

1. **File Type**: Check file extension and MIME type
```typescript
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];

function validateFile(file: File): { valid: boolean; error?: string } {
  // Check MIME type
  if (!ALLOWED_TYPES.includes(file.type)) {
    return { valid: false, error: 'Invalid file type. Please upload JPEG, PNG, or WebP.' };
  }
  
  // Check file size (10MB)
  const MAX_SIZE = 10 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    return { valid: false, error: 'File too large. Maximum size is 10MB.' };
  }
  
  return { valid: true };
}
```

2. **File Size**: Ensure ≤ 10MB
3. **File Extension**: Match MIME type

### Backend Validation

The Supabase bucket configuration enforces:
- MIME type restrictions (only JPEG, PNG, WebP)
- File size limit (10MB hard limit)
- Path validation (via RLS policies)

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "new row violates check constraint" | File exceeds 10MB | Compress image or use smaller file |
| "Policy violation" | Uploading to another user's folder | Ensure path starts with correct user_id |
| "Invalid MIME type" | Unsupported image format | Convert to JPEG, PNG, or WebP |
| "Storage quota exceeded" | User exceeded storage limit | Delete old images or upgrade plan |

## Performance Considerations

### Image Optimization

1. **Client-Side Compression**: Compress images before upload to reduce transfer time
```typescript
import imageCompression from 'browser-image-compression';

async function compressImage(file: File): Promise<File> {
  const options = {
    maxSizeMB: 2,
    maxWidthOrHeight: 1920,
    useWebWorker: true
  };
  
  return await imageCompression(file, options);
}
```

2. **Lazy Loading**: Use lazy loading for memorial page with many images
```typescript
<img 
  src={cat.avatar_url} 
  loading="lazy"
  alt={cat.name}
/>
```

3. **CDN Caching**: Supabase storage uses CDN - images are cached globally

### Storage Limits

- **Free Tier**: 1GB storage, 2GB bandwidth
- **Pro Tier**: 100GB storage, 200GB bandwidth
- **Recommendation**: Monitor usage, implement cleanup for old/unused images

## Security Best Practices

1. **Never expose service key** in frontend code
2. **Always validate files** client-side before upload (UX + cost saving)
3. **Use authenticated requests** for uploads (enforced by RLS)
4. **Audit access logs** regularly for suspicious activity
5. **Rotate service keys** periodically

## Testing Checklist

- [ ] Upload JPEG image (< 10MB) - should succeed
- [ ] Upload PNG image (< 10MB) - should succeed
- [ ] Upload WebP image (< 10MB) - should succeed
- [ ] Upload file > 10MB - should fail with error
- [ ] Upload unsupported format (e.g., GIF) - should fail
- [ ] Upload to own folder as authenticated user - should succeed
- [ ] Attempt to upload to another user's folder - should fail (RLS)
- [ ] View public image URL without authentication - should succeed
- [ ] Delete own image - should succeed
- [ ] Attempt to delete another user's image - should fail (RLS)

## Migration Instructions

To apply this storage bucket setup to your Supabase project:

### Option 1: Supabase Dashboard (Recommended for first-time setup)

1. Log in to [Supabase Dashboard](https://app.supabase.com)
2. Navigate to **Storage** in the left sidebar
3. Click **New bucket**
4. Configure:
   - Name: `cat-images`
   - Public: ✅ Enabled
   - File size limit: `10485760` (bytes)
   - Allowed MIME types: `image/jpeg, image/png, image/webp`
5. Click **Create bucket**
6. Navigate to **Storage** > **Policies**
7. Click **New policy** for each policy in `storage_setup.sql`

### Option 2: SQL Script (Automated)

1. Open Supabase Dashboard
2. Navigate to **SQL Editor**
3. Copy contents of `supabase/storage_setup.sql`
4. Paste into SQL Editor
5. Click **Run** to execute

### Option 3: Supabase CLI (For CI/CD)

```bash
# Install Supabase CLI
npm install -g supabase

# Link to your project
supabase link --project-ref your-project-ref

# Run migration
supabase db push

# Or run specific file
psql $DATABASE_URL < supabase/storage_setup.sql
```

## Troubleshooting

### Issue: "Bucket already exists" error

**Solution**: The script includes `ON CONFLICT` handling. If you see this error, it means the bucket exists but may have different configuration. Update the script to use `UPDATE` instead of `INSERT`.

### Issue: Policies not applying

**Solution**: 
1. Check that RLS is enabled on `storage.objects` table
2. Verify policy names don't conflict with existing policies
3. Use `DROP POLICY IF EXISTS` before creating

### Issue: Public URLs returning 404

**Solution**:
1. Verify bucket `public` setting is `true`
2. Check file actually exists using Supabase Dashboard
3. Ensure URL format is correct: `{supabase_url}/storage/v1/object/public/cat-images/{path}`

## Future Enhancements

- [ ] Image transformation (thumbnails, different sizes)
- [ ] Automatic cleanup of orphaned images (images with no associated cat)
- [ ] Image moderation (detect inappropriate content)
- [ ] Support for animated images (GIF, APNG)
- [ ] Multi-region replication for faster global access
- [ ] Compression service integration (automatic optimization)

## References

- [Supabase Storage Documentation](https://supabase.com/docs/guides/storage)
- [Supabase Storage RLS](https://supabase.com/docs/guides/storage/security/access-control)
- Requirements: 1.1, 1.2, 5.2
- Design Document: Section "Image Validation", "Avatar Image Generation"
