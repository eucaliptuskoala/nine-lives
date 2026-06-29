-- Nine Lives — Storage Bucket Setup for Cat Images
-- This script sets up the Supabase storage bucket for cat photo uploads

-- Create the cat-images storage bucket
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'cat-images',
    'cat-images',
    true, -- Enable public access for reading images
    10485760, -- 10MB file size limit (10 * 1024 * 1024 bytes)
    ARRAY['image/jpeg', 'image/png', 'image/webp'] -- Allowed image formats
)
ON CONFLICT (id) DO UPDATE SET
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Storage policies for cat-images bucket

-- Policy 1: Allow authenticated users to upload to their own folder (user_id/)
-- Users can only upload to paths that start with their user ID
CREATE POLICY "Users can upload to their own folder"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'cat-images' AND
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy 2: Allow authenticated users to update their own files
CREATE POLICY "Users can update their own files"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
    bucket_id = 'cat-images' AND
    (storage.foldername(name))[1] = auth.uid()::text
)
WITH CHECK (
    bucket_id = 'cat-images' AND
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy 3: Allow authenticated users to delete their own files
CREATE POLICY "Users can delete their own files"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'cat-images' AND
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Policy 4: Allow public read access to all images in the bucket
-- This enables viewing of cat avatars and source images in the UI
CREATE POLICY "Public read access for all images"
ON storage.objects
FOR SELECT
TO public
USING (bucket_id = 'cat-images');
