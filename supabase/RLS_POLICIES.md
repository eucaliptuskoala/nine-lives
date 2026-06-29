# Row Level Security (RLS) Policies

This document describes the Row Level Security policies implemented for the Nine Lives database.

## Overview

RLS policies ensure that users can only access their own data. This is critical for data isolation and security in a multi-tenant application.

## Enabled Tables

RLS is enabled on the following tables:
- `cat`
- `game_run`
- `ability`

## Cat Table Policies

### Policy: cat_select
**Operation:** SELECT  
**Rule:** Users can only read their own cats  
**Implementation:** `USING (user_id = auth.uid())`

### Policy: cat_insert
**Operation:** INSERT  
**Rule:** Users can only insert cats with their own user_id  
**Implementation:** `WITH CHECK (user_id = auth.uid())`

### Policy: cat_update
**Operation:** UPDATE  
**Rule:** Users can only update their own cats  
**Implementation:** `USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())`

### Policy: cat_delete
**Operation:** DELETE  
**Rule:** Users can only delete their own cats  
**Implementation:** `USING (user_id = auth.uid())`

## Game Run Table Policies

Game runs are accessible based on the user_id field - users can only access their own game runs.

### Policy: game_run_select
**Operation:** SELECT  
**Rule:** Users can only read their own game runs  
**Implementation:** `USING (user_id = auth.uid())`

### Policy: game_run_insert
**Operation:** INSERT  
**Rule:** Users can only create game runs with their own user_id  
**Implementation:** `WITH CHECK (user_id = auth.uid())`

### Policy: game_run_update
**Operation:** UPDATE  
**Rule:** Users can only update their own game runs  
**Implementation:** `USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())`

### Policy: game_run_delete
**Operation:** DELETE  
**Rule:** Users can only delete their own game runs  
**Implementation:** `USING (user_id = auth.uid())`

## Ability Table Policies

Abilities are accessible based on cat ownership - users can only access abilities for cats they own.

### Policy: ability_select
**Operation:** SELECT  
**Rule:** Users can only read abilities for their own cats  
**Implementation:** `USING (creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid()))`

### Policy: ability_insert
**Operation:** INSERT  
**Rule:** Users can only create abilities for their own cats  
**Implementation:** `WITH CHECK (creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid()))`

### Policy: ability_update
**Operation:** UPDATE  
**Rule:** Users can only update abilities for their own cats  
**Implementation:** `USING (creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())) WITH CHECK (creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid()))`

### Policy: ability_delete
**Operation:** DELETE  
**Rule:** Users can only delete abilities for their own cats  
**Implementation:** `USING (creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid()))`

## Requirements Validation

These policies satisfy the following requirements:

- **Requirement 23.1:** Users can only query their own cats (user_id matches auth.uid())
- **Requirement 23.2:** Users cannot access cats belonging to other users (enforced via RLS)
- **Requirement 23.3:** Users can only query game_runs associated with their own cats (enforced via JOIN with cats table)

## Testing the Policies

### Manual Testing Steps

To verify RLS policies work correctly, you need two test users.

#### Setup
1. Create two test users in Supabase Auth:
   - User A: `test-user-a@example.com`
   - User B: `test-user-b@example.com`

2. Sign in as User A and create a cat:
```sql
-- Get User A's auth.uid() - you'll need this
SELECT auth.uid();

-- Create a cat as User A
INSERT INTO cat (
  user_id, name, breed, class, current_hp, max_hp, 
  dmg, def, spd, mana, max_mana, lore, avatar_url, 
  source_image_url, status, lives_remaining
) VALUES (
  auth.uid(), 'Fluffy', 'Persian', 'STRENGTH', 
  100, 100, 25, 15, 20, 100, 100, 
  'A brave warrior cat', 'https://example.com/avatar.jpg',
  'https://example.com/source.jpg', 'ALIVE', 9
);
```

#### Test 1: Cat SELECT Policy
```sql
-- As User A: Should see the cat
SELECT * FROM cat WHERE name = 'Fluffy';
-- Expected: 1 row returned

-- Sign out and sign in as User B
-- As User B: Should NOT see User A's cat
SELECT * FROM cat WHERE name = 'Fluffy';
-- Expected: 0 rows returned
```

#### Test 2: Cat INSERT Policy
```sql
-- As User B: Try to insert a cat with User A's user_id
INSERT INTO cat (
  user_id, name, breed, class, current_hp, max_hp, 
  dmg, def, spd, mana, max_mana, lore, avatar_url, 
  source_image_url, status, lives_remaining
) VALUES (
  '<user-a-uuid>', 'Hacker Cat', 'Siamese', 'AGILITY', 
  50, 50, 30, 10, 40, 80, 80, 
  'An unauthorized cat', 'https://example.com/hacker.jpg',
  'https://example.com/source2.jpg', 'ALIVE', 9
);
-- Expected: Policy violation error
```

#### Test 3: Cat UPDATE Policy
```sql
-- As User B: Try to update User A's cat
UPDATE cat SET name = 'Stolen Cat' WHERE name = 'Fluffy';
-- Expected: 0 rows updated (policy prevents access)

-- As User A: Update own cat
UPDATE cat SET name = 'Fluffy Updated' WHERE name = 'Fluffy';
-- Expected: 1 row updated successfully
```

#### Test 4: Ability Policies (via cat ownership)
```sql
-- As User A: Create an ability for Fluffy
INSERT INTO ability (
  creature_id, name, dmg, type, cooldown, mana_cost, 
  lore, is_special, description
) VALUES (
  (SELECT id FROM cat WHERE name = 'Fluffy Updated'),
  'Claw Swipe', 25, 'DMG', 2, 30,
  'A powerful swipe', FALSE, 'Deals 25 damage'
);

-- As User A: Should see the ability
SELECT * FROM ability WHERE name = 'Claw Swipe';
-- Expected: 1 row returned

-- Sign in as User B
-- As User B: Should NOT see User A's ability
SELECT * FROM ability WHERE name = 'Claw Swipe';
-- Expected: 0 rows returned
```

#### Test 5: Game Run Policies (via cat ownership)
```sql
-- As User A: Create a game run for Fluffy
INSERT INTO game_run (cat_id, status, current_round)
VALUES (
  (SELECT id FROM cat WHERE name = 'Fluffy Updated'),
  'IN_PROGRESS', 1
);

-- As User A: Should see the game run
SELECT * FROM game_run WHERE cat_id = (SELECT id FROM cat WHERE name = 'Fluffy Updated');
-- Expected: 1 row returned

-- Sign in as User B
-- As User B: Should NOT see User A's game run
SELECT * FROM game_run WHERE cat_id = (SELECT id FROM cat WHERE name = 'Fluffy Updated');
-- Expected: 0 rows returned (policy blocks access)
```

#### Test 6: Game Run INSERT with user_id
```sql
-- As User A: Create a game run without cat_id (digitizing phase)
INSERT INTO game_run (user_id, status, current_round)
VALUES (auth.uid(), 'DIGITIZING', 1);
-- Expected: Success

-- As User A: Update the game run to link it to a cat
UPDATE game_run 
SET cat_id = (SELECT id FROM cat WHERE name = 'Fluffy Updated'),
    status = 'IN_PROGRESS'
WHERE status = 'DIGITIZING' 
AND cat_id IS NULL 
AND user_id = auth.uid()
LIMIT 1;
-- Expected: Success
```

### Automated Testing

For automated testing, you would need to:

1. Create a test suite that uses the Supabase client
2. Authenticate as different users programmatically
3. Attempt operations and verify they succeed/fail as expected

Example test structure (pseudocode):
```typescript
describe('RLS Policies', () => {
  test('User can only see their own cats', async () => {
    const userA = await createTestUser('user-a@test.com');
    const userB = await createTestUser('user-b@test.com');
    
    // User A creates a cat
    const catA = await createCat(userA);
    
    // User A can see their cat
    const catsForA = await getCats(userA);
    expect(catsForA).toHaveLength(1);
    
    // User B cannot see User A's cat
    const catsForB = await getCats(userB);
    expect(catsForB).toHaveLength(0);
  });
  
  // ... more tests
});
```

## Troubleshooting

### Common Issues

1. **Policy not working**: Make sure RLS is enabled on the table
   ```sql
   ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;
   ```

2. **Policies too restrictive**: If you can't access your own data, check:
   - You're authenticated (auth.uid() is not null)
   - The user_id in your data matches auth.uid()

3. **Service role bypasses RLS**: The service role key bypasses all RLS policies. For testing, use the anon key or a user JWT.

## Implementation Notes

- All policies use `auth.uid()` which returns the authenticated user's ID from the JWT token
- The `USING` clause determines which rows can be accessed for SELECT, UPDATE, DELETE
- The `WITH CHECK` clause determines which rows can be inserted or what values can be set during UPDATE
- For game_runs and abilities, we use a subquery to check cat ownership rather than direct user_id comparison
- The game_run INSERT policy allows NULL cat_id to support the DIGITIZING phase before a cat is created
