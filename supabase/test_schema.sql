-- Test file to verify database schema and constraints
-- This file contains test cases to validate the database schema implementation

-- Test 1: Valid cat creation with all required fields and constraints satisfied
-- Expected: Success
INSERT INTO cat (
    user_id, name, breed, class, 
    current_hp, max_hp, dmg, def, spd, 
    mana, max_mana, lore, avatar_url, source_image_url
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Shadow',
    'Siamese',
    'AGILITY',
    100, 100, 25, 15, 35,
    150, 150, 
    'A mysterious cat with lightning reflexes',
    'https://example.com/avatar.png',
    'https://example.com/source.jpg'
);

-- Test 2: Cat with HP out of bounds (should fail)
-- Expected: Constraint violation - cat_hp_bounds
-- INSERT INTO cat (
--     user_id, name, breed, class, 
--     current_hp, max_hp, dmg, def, spd, 
--     mana, max_mana, lore, avatar_url, source_image_url
-- ) VALUES (
--     '00000000-0000-0000-0000-000000000001'::uuid,
--     'Invalid HP Cat',
--     'Persian',
--     'STRENGTH',
--     250, 250, 25, 15, 35,
--     150, 150, 
--     'This should fail',
--     'https://example.com/avatar.png',
--     'https://example.com/source.jpg'
-- );

-- Test 3: Cat with lives_remaining out of bounds (should fail)
-- Expected: Constraint violation - cat_lives_bounds
-- INSERT INTO cat (
--     user_id, name, breed, class, 
--     current_hp, max_hp, dmg, def, spd, 
--     mana, max_mana, lore, avatar_url, source_image_url,
--     lives_remaining
-- ) VALUES (
--     '00000000-0000-0000-0000-000000000001'::uuid,
--     'Too Many Lives',
--     'Tabby',
--     'INTELLIGENCE',
--     100, 100, 25, 15, 35,
--     150, 150, 
--     'This should fail',
--     'https://example.com/avatar.png',
--     'https://example.com/source.jpg',
--     10
-- );

-- Test 4: Valid game_run creation
-- Expected: Success
INSERT INTO game_run (
    user_id, cat_id, status, current_round, state
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    (SELECT id FROM cat WHERE name = 'Shadow' LIMIT 1),
    'IN_PROGRESS',
    1,
    '{
        "player_hp": 100,
        "player_max_hp": 100,
        "player_mana": 150,
        "player_max_mana": 150,
        "player_is_defending": false,
        "player_shield": 0,
        "lives_remaining": 9,
        "player_ability_cooldowns": {},
        "phase": "PLAYER_TURN",
        "current_round": 1,
        "enemy": {
            "name": "Shadow Beast",
            "breed": "Unknown",
            "hp": 25,
            "max_hp": 25,
            "atk": 10,
            "def": 7,
            "spd": 9,
            "mana": 48,
            "max_mana": 80,
            "ability_cooldowns": {},
            "abilities": [],
            "avatar_url": "https://example.com/enemy.png"
        }
    }'::jsonb
);

-- Test 5: Valid ability creation
-- Expected: Success
INSERT INTO ability (
    creature_id, name, dmg, type, effect,
    cooldown, mana_cost, lore, is_special, description
) VALUES (
    (SELECT id FROM cat WHERE name = 'Shadow' LIMIT 1),
    'Shadow Strike',
    40,
    'DMG',
    'BLIND',
    3,
    50,
    'Strikes from the shadows with deadly precision',
    false,
    'Deals 40 damage and may blind the enemy'
);

-- Test 6: Ability with invalid cooldown (should fail)
-- Expected: Constraint violation - ability_cooldown_bounds
-- INSERT INTO ability (
--     creature_id, name, dmg, type,
--     cooldown, mana_cost, lore, is_special, description
-- ) VALUES (
--     (SELECT id FROM cat WHERE name = 'Shadow' LIMIT 1),
--     'Invalid Cooldown',
--     40,
--     'DMG',
--     10,
--     50,
--     'This should fail',
--     false,
--     'Invalid cooldown ability'
-- );

-- Test 7: Ability with invalid mana cost (should fail)
-- Expected: Constraint violation - ability_mana_cost_bounds
-- INSERT INTO ability (
--     creature_id, name, dmg, type,
--     cooldown, mana_cost, lore, is_special, description
-- ) VALUES (
--     (SELECT id FROM cat WHERE name = 'Shadow' LIMIT 1),
--     'Invalid Mana Cost',
--     40,
--     'DMG',
--     3,
--     150,
--     'This should fail',
--     false,
--     'Invalid mana cost ability'
-- );

-- Verify indexes exist
SELECT 
    tablename,
    indexname,
    indexdef
FROM 
    pg_indexes
WHERE 
    tablename IN ('cat', 'game_run', 'ability')
ORDER BY 
    tablename, indexname;

-- Verify constraints exist
SELECT
    conname AS constraint_name,
    conrelid::regclass AS table_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS constraint_definition
FROM
    pg_constraint
WHERE
    conrelid IN ('cat'::regclass, 'game_run'::regclass, 'ability'::regclass)
ORDER BY
    table_name, constraint_name;

-- Cleanup test data
DELETE FROM ability WHERE creature_id IN (SELECT id FROM cat WHERE name = 'Shadow');
DELETE FROM game_run WHERE cat_id IN (SELECT id FROM cat WHERE name = 'Shadow');
DELETE FROM cat WHERE name = 'Shadow';
