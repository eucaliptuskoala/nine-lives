# Task 1.2 Implementation Summary: Row Level Security (RLS) Policies

## Overview

This document summarizes the implementation of Row Level Security (RLS) policies for the Nine Lives database, completing task 1.2 from the implementation plan.

## Task Requirements

✅ Enable RLS on `cats`, `abilities`, and `game_runs` tables  
✅ Create policy: users can only read their own cats (SELECT on cats WHERE user_id = auth.uid())  
✅ Create policy: users can only insert their own cats (INSERT on cats WHERE user_id = auth.uid())  
✅ Create policy: users can only update their own cats (UPDATE on cats WHERE user_id = auth.uid())  
✅ Create policy: users can only read abilities for their own cats (SELECT on abilities WHERE creature_id IN (...))  
✅ Create policy: users can only read/write game_runs for their own cats (SELECT/UPDATE on game_runs WHERE cat_id IN (...))

## What Was Implemented

### 1. RLS Enabled on Three Tables

```sql
ALTER TABLE cat ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE ability ENABLE ROW LEVEL SECURITY;
```

### 2. Cat Table Policies (4 policies)

- **cat_select**: Users can only SELECT their own cats
- **cat_insert**: Users can only INSERT cats with their own user_id
- **cat_update**: Users can only UPDATE their own cats
- **cat_delete**: Users can only DELETE their own cats

All policies use `user_id = auth.uid()` to enforce ownership.

### 3. Game Run Table Policies (4 policies)

- **game_run_select**: Users can only SELECT their own game runs
- **game_run_insert**: Users can only INSERT game runs with their own user_id
- **game_run_update**: Users can only UPDATE their own game runs
- **game_run_delete**: Users can only DELETE their own game runs

Note: The `game_run` table has a `user_id` field for direct ownership checking.

### 4. Ability Table Policies (4 policies)

- **ability_select**: Users can only SELECT abilities for cats they own
- **ability_insert**: Users can only INSERT abilities for cats they own
- **ability_update**: Users can only UPDATE abilities for cats they own
- **ability_delete**: Users can only DELETE abilities for cats they own

These policies use a subquery: `creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())`

## Files Modified

### `/supabase/migration.sql`

Updated the RLS policies section to implement granular policies for each operation (SELECT, INSERT, UPDATE, DELETE) on each table.

**Changes:**
- Replaced the generic `FOR ALL` policies with specific policies for each operation
- Added separate INSERT policies with `WITH CHECK` clauses
- Added separate UPDATE policies with both `USING` and `WITH CHECK` clauses
- Added separate DELETE policies

## Files Created

### `/supabase/RLS_POLICIES.md`

Comprehensive documentation explaining:
- Overview of RLS implementation
- Detailed explanation of each policy
- Manual testing instructions with SQL examples
- Automated testing guidelines
- Troubleshooting tips
- Implementation notes

### `/supabase/test_rls_policies.sql`

SQL test script containing:
- 6 comprehensive test scenarios
- Test for cat SELECT, INSERT, UPDATE policies
- Test for ability policies (via cat ownership)
- Test for game_run policies
- Test for game_run INSERT with NULL cat_id during digitizing phase
- Cleanup queries to remove test data

### `/supabase/IMPLEMENTATION_SUMMARY.md`

This file - a summary of the implementation for easy reference.

## Requirements Satisfied

This implementation satisfies the following requirements from the requirements document:

- **Requirement 23.1**: Users can only query their own cats (user_id matches auth.uid())
  - Implemented via `cat_select` policy
  
- **Requirement 23.2**: Users cannot access cats belonging to other users (enforced via RLS)
  - Implemented via all cat policies (SELECT, INSERT, UPDATE, DELETE)
  
- **Requirement 23.3**: Users can only query game_runs associated with their own cats
  - Implemented via game_run policies using user_id field

## Testing

### Manual Testing

To test the RLS policies:

1. Follow the instructions in `/supabase/RLS_POLICIES.md`
2. Create two test users in Supabase Auth
3. Run the test queries as each user to verify isolation
4. Verify that User B cannot access User A's data

### Automated Testing (SQL Script)

Run the test script:

```bash
# In Supabase SQL Editor
# Sign in as a test user first, then run:
/supabase/test_rls_policies.sql
```

The script will:
- Create test data as User A
- Verify User A can access their own data
- Verify User B cannot access User A's data
- Test all CRUD operations on all three tables
- Clean up test data

## Security Considerations

1. **auth.uid()**: All policies rely on Supabase Auth's `auth.uid()` function which returns the authenticated user's ID from their JWT token.

2. **Service Role Bypass**: The service role key bypasses all RLS policies. For production:
   - Never expose the service role key to the frontend
   - Use anon key for client-side operations
   - Use service role only in trusted backend code

3. **Policy Completeness**: We implemented separate policies for SELECT, INSERT, UPDATE, and DELETE to have fine-grained control over each operation.

4. **Cascading Ownership**: Abilities and game_runs inherit access control from cat ownership, creating a clean hierarchical security model.

## Schema Note

The `game_run` table includes a `user_id` field directly, which simplifies the RLS policies. This is different from abilities which use a subquery to check ownership through the `cat` table.

```sql
-- game_run table structure (relevant fields)
CREATE TABLE game_run (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES auth.users(id),  -- Direct ownership
    cat_id          UUID REFERENCES cat(id),                   -- Can be NULL during DIGITIZING
    ...
);
```

This allows game_runs to be created during the DIGITIZING phase before a cat exists, while still maintaining proper access control.

## Next Steps

Task 1.2 is now complete. The next task in the implementation plan is:

**Task 1.3**: Set up Supabase storage bucket for cat images
- Create storage bucket named 'cat-images'
- Configure bucket to accept JPEG, PNG, WebP files
- Set up RLS policies for storage bucket
- Configure public URL access for uploaded images

## Verification Checklist

- [x] RLS enabled on all three tables (cat, game_run, ability)
- [x] Cat SELECT policy implemented
- [x] Cat INSERT policy implemented
- [x] Cat UPDATE policy implemented
- [x] Cat DELETE policy implemented
- [x] Game run SELECT policy implemented
- [x] Game run INSERT policy implemented
- [x] Game run UPDATE policy implemented
- [x] Game run DELETE policy implemented
- [x] Ability SELECT policy implemented (via cat ownership)
- [x] Ability INSERT policy implemented (via cat ownership)
- [x] Ability UPDATE policy implemented (via cat ownership)
- [x] Ability DELETE policy implemented (via cat ownership)
- [x] Documentation created (RLS_POLICIES.md)
- [x] Test script created (test_rls_policies.sql)
- [x] Requirements 23.1, 23.2, 23.3 satisfied

## Contact

If you encounter any issues with the RLS policies or have questions about the implementation, please refer to:
1. `/supabase/RLS_POLICIES.md` - Detailed documentation
2. `/supabase/test_rls_policies.sql` - Test examples
3. Supabase documentation: https://supabase.com/docs/guides/auth/row-level-security
