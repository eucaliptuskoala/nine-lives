-- RLS Policy Test Script
-- This script tests the Row Level Security policies for the Nine Lives database
-- Run this script in the Supabase SQL Editor with different authenticated users

-- ============================================================================
-- SETUP: Create Test Users and Data
-- ============================================================================

-- Note: You must create test users in Supabase Auth first:
-- 1. Go to Authentication > Users in Supabase Dashboard
-- 2. Create two test users (e.g., test-a@example.com and test-b@example.com)
-- 3. Sign in as each user to run the tests below

-- ============================================================================
-- TEST 1: Cat SELECT Policy
-- ============================================================================

-- As User A: Create a test cat
DO $$
DECLARE
  v_cat_id UUID;
BEGIN
  INSERT INTO cat (
    user_id, name, breed, class, current_hp, max_hp,
    dmg, def, spd, mana, max_mana, lore, avatar_url,
    source_image_url, status, lives_remaining
  ) VALUES (
    auth.uid(),
    'Test Cat A',
    'Persian',
    'STRENGTH',
    100, 100, 25, 15, 20, 100, 100,
    'A test cat for User A',
    'https://example.com/avatar-a.jpg',
    'https://example.com/source-a.jpg',
    'ALIVE',
    9
  ) RETURNING id INTO v_cat_id;
  
  RAISE NOTICE 'Created cat with ID: %', v_cat_id;
END $$;

-- As User A: Verify you can see your own cat
SELECT 
  'TEST 1A: User A can SELECT their own cat' AS test_name,
  CASE 
    WHEN COUNT(*) = 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM cat 
WHERE name = 'Test Cat A';

-- As User B (sign in as different user): Verify you CANNOT see User A's cat
-- This should return 0 rows
SELECT 
  'TEST 1B: User B cannot SELECT User A''s cat' AS test_name,
  CASE 
    WHEN COUNT(*) = 0 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM cat 
WHERE name = 'Test Cat A';

-- ============================================================================
-- TEST 2: Cat INSERT Policy
-- ============================================================================

-- As User A: Create a cat with your own user_id (should succeed)
INSERT INTO cat (
  user_id, name, breed, class, current_hp, max_hp,
  dmg, def, spd, mana, max_mana, lore, avatar_url,
  source_image_url, status, lives_remaining
) VALUES (
  auth.uid(),
  'Valid Insert Test',
  'Siamese',
  'AGILITY',
  80, 80, 30, 10, 40, 90, 90,
  'Valid insert with correct user_id',
  'https://example.com/avatar-valid.jpg',
  'https://example.com/source-valid.jpg',
  'ALIVE',
  9
);

SELECT 
  'TEST 2: User can INSERT cat with own user_id' AS test_name,
  CASE 
    WHEN COUNT(*) = 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM cat 
WHERE name = 'Valid Insert Test';

-- Clean up
DELETE FROM cat WHERE name = 'Valid Insert Test';

-- Note: Attempting to INSERT with a different user_id will fail with a policy violation
-- This cannot be tested in a single script as it requires a different user_id value

-- ============================================================================
-- TEST 3: Cat UPDATE Policy
-- ============================================================================

-- As User A: Update your own cat (should succeed)
UPDATE cat 
SET name = 'Test Cat A Updated'
WHERE name = 'Test Cat A';

SELECT 
  'TEST 3A: User A can UPDATE their own cat' AS test_name,
  CASE 
    WHEN COUNT(*) = 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM cat 
WHERE name = 'Test Cat A Updated';

-- As User B (sign in as different user): Try to update User A's cat
-- This should update 0 rows due to RLS policy
UPDATE cat 
SET name = 'Hacked Cat Name'
WHERE name = 'Test Cat A Updated';

-- Verify the name wasn't changed (as User A)
SELECT 
  'TEST 3B: User B cannot UPDATE User A''s cat' AS test_name,
  CASE 
    WHEN name = 'Test Cat A Updated' THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM cat 
WHERE name = 'Test Cat A Updated' OR name = 'Hacked Cat Name';

-- ============================================================================
-- TEST 4: Ability Policies (via cat ownership)
-- ============================================================================

-- As User A: Create an ability for your cat
DO $$
DECLARE
  v_cat_id UUID;
BEGIN
  SELECT id INTO v_cat_id 
  FROM cat 
  WHERE name = 'Test Cat A Updated' 
  LIMIT 1;
  
  INSERT INTO ability (
    creature_id, name, dmg, type, cooldown, mana_cost,
    lore, is_special, description
  ) VALUES (
    v_cat_id,
    'Test Ability A',
    25,
    'DMG',
    2,
    30,
    'A test ability',
    FALSE,
    'Deals 25 damage'
  );
  
  RAISE NOTICE 'Created ability for cat ID: %', v_cat_id;
END $$;

-- As User A: Verify you can see your own cat's abilities
SELECT 
  'TEST 4A: User A can SELECT abilities for their own cat' AS test_name,
  CASE 
    WHEN COUNT(*) >= 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM ability 
WHERE name = 'Test Ability A';

-- As User B (sign in as different user): Verify you CANNOT see User A's abilities
SELECT 
  'TEST 4B: User B cannot SELECT User A''s abilities' AS test_name,
  CASE 
    WHEN COUNT(*) = 0 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM ability 
WHERE name = 'Test Ability A';

-- ============================================================================
-- TEST 5: Game Run Policies (via cat ownership)
-- ============================================================================

-- As User A: Create a game run for your cat
DO $$
DECLARE
  v_cat_id UUID;
  v_game_run_id UUID;
BEGIN
  SELECT id INTO v_cat_id 
  FROM cat 
  WHERE name = 'Test Cat A Updated' 
  LIMIT 1;
  
  INSERT INTO game_run (user_id, cat_id, status, current_round)
  VALUES (auth.uid(), v_cat_id, 'IN_PROGRESS', 1)
  RETURNING id INTO v_game_run_id;
  
  RAISE NOTICE 'Created game_run with ID: %', v_game_run_id;
END $$;

-- As User A: Verify you can see your own game runs
SELECT 
  'TEST 5A: User A can SELECT game_runs for their own cat' AS test_name,
  CASE 
    WHEN COUNT(*) >= 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM game_run gr
JOIN cat c ON gr.cat_id = c.id
WHERE c.name = 'Test Cat A Updated';

-- As User B (sign in as different user): Verify you CANNOT see User A's game runs
SELECT 
  'TEST 5B: User B cannot SELECT User A''s game_runs' AS test_name,
  CASE 
    WHEN COUNT(*) = 0 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM game_run gr
WHERE gr.cat_id IN (
  SELECT id FROM cat WHERE name = 'Test Cat A Updated'
);

-- ============================================================================
-- TEST 6: Game Run INSERT with user_id (DIGITIZING phase)
-- ============================================================================

-- As User A: Create a game run without cat_id (should succeed)
INSERT INTO game_run (user_id, status, current_round)
VALUES (auth.uid(), 'DIGITIZING', 1);

SELECT 
  'TEST 6A: User can INSERT game_run with user_id and NULL cat_id' AS test_name,
  CASE 
    WHEN COUNT(*) >= 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM game_run 
WHERE status = 'DIGITIZING' AND cat_id IS NULL;

-- As User A: Update the game run to link it to your cat
DO $$
DECLARE
  v_cat_id UUID;
  v_game_run_id UUID;
BEGIN
  SELECT id INTO v_cat_id 
  FROM cat 
  WHERE name = 'Test Cat A Updated' 
  LIMIT 1;
  
  SELECT id INTO v_game_run_id
  FROM game_run
  WHERE status = 'DIGITIZING' AND cat_id IS NULL AND user_id = auth.uid()
  LIMIT 1;
  
  UPDATE game_run 
  SET cat_id = v_cat_id, status = 'IN_PROGRESS'
  WHERE id = v_game_run_id;
  
  RAISE NOTICE 'Updated game_run % with cat_id %', v_game_run_id, v_cat_id;
END $$;

SELECT 
  'TEST 6B: User can UPDATE game_run to link their cat' AS test_name,
  CASE 
    WHEN COUNT(*) >= 1 THEN 'PASS'
    ELSE 'FAIL'
  END AS result
FROM game_run 
WHERE status = 'IN_PROGRESS' AND cat_id IS NOT NULL;

-- ============================================================================
-- CLEANUP: Remove test data
-- ============================================================================

-- As User A: Clean up test data
DELETE FROM game_run 
WHERE cat_id IN (
  SELECT id FROM cat WHERE name = 'Test Cat A Updated'
);

DELETE FROM ability 
WHERE creature_id IN (
  SELECT id FROM cat WHERE name = 'Test Cat A Updated'
);

DELETE FROM cat 
WHERE name = 'Test Cat A Updated';

-- ============================================================================
-- SUMMARY
-- ============================================================================

-- Run this query to see all test results
-- (This requires running all tests above first)
SELECT 
  'RLS Policy Tests Complete' AS summary,
  'Check PASS/FAIL results above' AS note;
