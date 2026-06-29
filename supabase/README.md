# Nine Lives - Supabase Database Setup

This directory contains all database migrations, storage configuration, and documentation for the Nine Lives game's Supabase backend.

## Files Overview

- **`migration.sql`** - Initial database schema (tables, enums, indexes, constraints, RLS policies)
- **`storage_setup.sql`** - Storage bucket configuration for cat images
- **`STORAGE_BUCKET_DOCUMENTATION.md`** - Comprehensive guide for the cat-images storage bucket

## Quick Start

### Prerequisites

1. Supabase account - [Sign up](https://app.supabase.com)
2. Supabase project created
3. Project credentials (URL and keys)

### Setup Steps

#### 1. Configure Environment Variables

**Backend** (`backend/.env`):
```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

**Frontend** (`frontend/.env`):
```env
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
```

#### 2. Run Database Migration

**Option A: Using Supabase Dashboard (Recommended)**

1. Log in to [Supabase Dashboard](https://app.supabase.com)
2. Navigate to **SQL Editor**
3. Copy and paste the contents of `migration.sql`
4. Click **Run** to execute

**Option B: Using Supabase CLI**

```bash
# Install CLI
npm install -g supabase

# Link to your project
supabase link --project-ref your-project-ref

# Run migration
psql $DATABASE_URL < supabase/migration.sql
```

#### 3. Set Up Storage Bucket

**Option A: Using Supabase Dashboard**

See detailed instructions in `STORAGE_BUCKET_DOCUMENTATION.md` under "Migration Instructions"

**Option B: Using SQL Editor**

1. Navigate to **SQL Editor** in Supabase Dashboard
2. Copy and paste the contents of `storage_setup.sql`
3. Click **Run** to execute

#### 4. Verify Setup

Run these checks in the SQL Editor:

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';

-- Check RLS is enabled
SELECT tablename, rowsecurity FROM pg_tables 
WHERE schemaname = 'public';

-- Check storage bucket exists
SELECT * FROM storage.buckets WHERE id = 'cat-images';

-- Check storage policies exist
SELECT * FROM pg_policies WHERE tablename = 'objects';
```

## Database Schema Overview

### Tables

1. **`cat`** - Playable cat characters created from user uploads
   - User ownership via `user_id`
   - Stats: HP, damage, defence, speed, mana
   - Status: ALIVE or MEMORIAL
   - Lives remaining (0-9)

2. **`game_run`** - Individual game sessions
   - Links to a cat
   - Tracks game status: DIGITIZING → IN_PROGRESS → COMPLETED
   - Stores game state as JSONB
   - Tracks current round

3. **`ability`** - Cat and enemy abilities
   - Links to a cat via `creature_id`
   - Types: DMG, HEAL, SHIELD, etc.
   - Mana cost and cooldown
   - Special flag for ultimate abilities

### Storage Bucket

- **`cat-images`** - Stores user-uploaded cat photos and AI-generated avatars
  - 10MB file size limit
  - Allowed formats: JPEG, PNG, WebP
  - Public read access, owner-only write access
  - Organized by user ID folders

## Security

### Row-Level Security (RLS)

All tables have RLS enabled to ensure data isolation:

- **Cats**: Users can only access their own cats
- **Game Runs**: Accessible only if user owns the associated cat
- **Abilities**: Accessible only if user owns the associated cat
- **Storage**: Users can upload/delete in their folder, everyone can read

### Authentication

- Uses Supabase Auth with JWT tokens
- Frontend uses anon key (public, rate-limited)
- Backend uses service key (full access, keep secret)

## Data Validation

### Database Constraints

The schema includes extensive validation:

- Cat stats must fall within balanced ranges (e.g., HP: 30-200)
- Ability costs and cooldowns are bounded
- Lives remaining: 0-9
- Personal notes: max 500 characters
- All text fields have length limits

### Application-Level Validation

Additional validation in frontend and backend:

- Image file type and size validation
- Stat generation within specified bounds
- State validation on load (HP, mana, phase)

## Common Operations

### Create a New Cat (Backend)

```python
cat_data = {
    "user_id": user_id,
    "name": "Whiskers",
    "breed": "Siamese",
    "class": "AGILITY",
    "current_hp": 100,
    "max_hp": 100,
    "dmg": 25,
    "def": 15,
    "spd": 30,
    "mana": 100,
    "max_mana": 100,
    "lore": "A swift and cunning hunter...",
    "avatar_url": "https://...",
    "source_image_url": "https://...",
}

result = supabase.table("cat").insert(cat_data).execute()
cat_id = result.data[0]["id"]
```

### Query User's Cats (Frontend)

```typescript
const { data: cats, error } = await supabase
  .from('cat')
  .select('*')
  .eq('user_id', userId)
  .eq('status', 'ALIVE');
```

### Load Game State (Frontend)

```typescript
const { data: gameRun, error } = await supabase
  .from('game_run')
  .select(`
    *,
    cat:cat_id (*)
  `)
  .eq('id', gameRunId)
  .single();
```

### Update Game State (Frontend)

```typescript
const { error } = await supabase
  .from('game_run')
  .update({ state: gameState })
  .eq('id', gameRunId);
```

## Testing

### Manual Tests

1. Create a test user in Supabase Dashboard
2. Insert a test cat via SQL Editor
3. Query the cat using the anon key (should work)
4. Try to query as a different user (should fail - RLS)
5. Upload an image to storage
6. Verify public URL works without authentication

### Automated Tests

See `backend/tests/` and `frontend/src/__tests__/` for test suites that validate:

- Database constraints
- RLS policies
- State persistence
- Image upload/download

## Monitoring

### Important Metrics to Track

1. **Storage Usage**: Monitor `cat-images` bucket size
2. **Database Size**: Watch for growth in game_run.state (JSONB)
3. **Connection Pool**: Ensure connections are properly closed
4. **Failed Queries**: Monitor logs for RLS violations
5. **Upload Errors**: Track storage API errors

### Supabase Dashboard

Access these in the dashboard:

- **Database** > **Tables**: Browse and edit data
- **Storage** > **cat-images**: View uploaded files
- **Authentication** > **Users**: Manage test users
- **Logs** > **Postgres Logs**: Debug query issues
- **Logs** > **Storage Logs**: Debug upload issues

## Backup and Recovery

### Automatic Backups

Supabase automatically backs up your database daily (Pro plan).

### Manual Backup

```bash
# Export database
pg_dump $DATABASE_URL > backup.sql

# Export storage bucket
supabase storage download-all cat-images ./backup/storage/
```

### Restore

```bash
# Restore database
psql $DATABASE_URL < backup.sql

# Restore storage
supabase storage upload-all cat-images ./backup/storage/
```

## Troubleshooting

### Issue: "relation does not exist"

**Cause**: Migration not run or table name incorrect

**Fix**: Run `migration.sql` in SQL Editor

### Issue: "permission denied for table"

**Cause**: RLS policy blocking access

**Fix**: Verify user is authenticated and owns the resource

### Issue: "new row violates check constraint"

**Cause**: Data doesn't meet validation rules

**Fix**: Check constraint errors in logs, adjust data to meet bounds

### Issue: Storage upload fails

**Cause**: File too large, wrong type, or path violation

**Fix**: 
- Check file is < 10MB
- Check file is JPEG/PNG/WebP
- Check path starts with user_id

## Migration History

| Version | Date | Description |
|---------|------|-------------|
| v1 | Initial | Base schema: cat, game_run, ability tables |
| v1.1 | Task 1.3 | Added cat-images storage bucket with RLS policies |

## Next Steps

After setup is complete:

1. ✅ Database tables created
2. ✅ Storage bucket configured
3. ⬜ Test authentication flow
4. ⬜ Run digitization pipeline end-to-end
5. ⬜ Test battle state persistence
6. ⬜ Verify memorial page loads cats

## Support

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Discord](https://discord.supabase.com)
- Project README: `../README.md`
- Storage Bucket Guide: `STORAGE_BUCKET_DOCUMENTATION.md`

## Related Requirements

- **Requirement 1.1**: Cat Photo Upload - uses cat-images bucket
- **Requirement 1.2**: File size validation (10MB limit)
- **Requirement 5.2**: Avatar image storage and public URLs
- **Requirement 23**: Data isolation via RLS policies
- **Requirement 24**: Authentication integration

## Design References

- **Design Document**: `.kiro/specs/nine-lives-complete-implementation/design.md`
- **Architecture Diagram**: Section "Architecture"
- **Data Models**: Section "Database Models"
- **Security**: Section "Security Considerations"
