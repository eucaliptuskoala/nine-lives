-- Nine Lives — initial schema

-- Enums
CREATE TYPE class AS ENUM ('STRENGTH', 'AGILITY', 'INTELLIGENCE');
CREATE TYPE cat_status AS ENUM ('ALIVE', 'MEMORIAL');
CREATE TYPE game_status AS ENUM ('DIGITIZING', 'IN_PROGRESS', 'COMPLETED');
CREATE TYPE phase AS ENUM ('PLAYER_TURN', 'ENEMY_TURN');
CREATE TYPE ability_type AS ENUM ('DMG', 'HEAL', 'STEAL', 'SHIELD', 'AOE', 'COUNTER', 'TRUE_DMG');
CREATE TYPE effect AS ENUM ('STUN', 'SILENCE', 'BLEED', 'BURN', 'BLIND', 'SLOW', 'TAUNT', 'REGEN');

-- Creature base (abstract — not a table, columns shared via inheritance)
-- Cat
CREATE TABLE cat (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    name            TEXT NOT NULL,
    breed           TEXT NOT NULL,
    class           class NOT NULL,
    current_hp      INT NOT NULL,
    max_hp          INT NOT NULL,
    dmg             INT NOT NULL,
    def             INT NOT NULL,
    spd             INT NOT NULL,
    mana            INT NOT NULL,
    max_mana        INT NOT NULL,
    lore            TEXT NOT NULL,
    avatar_url      TEXT NOT NULL,
    lives_remaining INT NOT NULL DEFAULT 9,
    source_image_url TEXT NOT NULL,
    status          cat_status NOT NULL DEFAULT 'ALIVE',
    wins            INT NOT NULL DEFAULT 0,
    death_date      TIMESTAMPTZ,
    personal_note   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Game run
CREATE TABLE game_run (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id),
    cat_id          UUID REFERENCES cat(id),
    status          game_status NOT NULL DEFAULT 'DIGITIZING',
    current_round   INT NOT NULL DEFAULT 1,
    state           JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

-- Ability
CREATE TABLE ability (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creature_id     UUID NOT NULL REFERENCES cat(id),
    name            TEXT NOT NULL,
    dmg             INT NOT NULL,
    type            ability_type NOT NULL,
    effect          effect,
    cooldown        INT NOT NULL,
    mana_cost       INT NOT NULL,
    lore            TEXT NOT NULL,
    is_special      BOOLEAN NOT NULL DEFAULT FALSE,
    description     TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_cat_user_id ON cat(user_id);
CREATE INDEX idx_cat_status ON cat(status);
CREATE INDEX idx_game_run_user_id ON game_run(user_id);
CREATE INDEX idx_game_run_cat_id ON game_run(cat_id);
CREATE INDEX idx_game_run_status ON game_run(status);
CREATE INDEX idx_ability_creature_id ON ability(creature_id);

-- Check Constraints

-- Cat constraints
ALTER TABLE cat ADD CONSTRAINT cat_name_not_empty CHECK (length(trim(name)) > 0);
ALTER TABLE cat ADD CONSTRAINT cat_name_length CHECK (length(name) <= 100);
ALTER TABLE cat ADD CONSTRAINT cat_hp_positive CHECK (max_hp > 0);
ALTER TABLE cat ADD CONSTRAINT cat_hp_bounds CHECK (max_hp >= 30 AND max_hp <= 200);
ALTER TABLE cat ADD CONSTRAINT cat_current_hp_bounds CHECK (current_hp >= 0 AND current_hp <= max_hp);
ALTER TABLE cat ADD CONSTRAINT cat_dmg_bounds CHECK (dmg >= 5 AND dmg <= 50);
ALTER TABLE cat ADD CONSTRAINT cat_def_bounds CHECK (def >= 3 AND def <= 40);
ALTER TABLE cat ADD CONSTRAINT cat_spd_bounds CHECK (spd >= 5 AND spd <= 50);
ALTER TABLE cat ADD CONSTRAINT cat_mana_bounds CHECK (mana >= 0 AND mana <= max_mana);
ALTER TABLE cat ADD CONSTRAINT cat_max_mana_bounds CHECK (max_mana >= 50 AND max_mana <= 200);
ALTER TABLE cat ADD CONSTRAINT cat_lives_bounds CHECK (lives_remaining >= 0 AND lives_remaining <= 9);
ALTER TABLE cat ADD CONSTRAINT cat_wins_non_negative CHECK (wins >= 0);
ALTER TABLE cat ADD CONSTRAINT cat_personal_note_length CHECK (personal_note IS NULL OR length(personal_note) <= 500);

-- Ability constraints
ALTER TABLE ability ADD CONSTRAINT ability_name_not_empty CHECK (length(trim(name)) > 0);
ALTER TABLE ability ADD CONSTRAINT ability_name_length CHECK (length(name) <= 50);
ALTER TABLE ability ADD CONSTRAINT ability_dmg_non_negative CHECK (dmg >= 0);
ALTER TABLE ability ADD CONSTRAINT ability_cooldown_bounds CHECK (cooldown >= 0 AND cooldown <= 5);
ALTER TABLE ability ADD CONSTRAINT ability_mana_cost_bounds CHECK (mana_cost >= 0 AND mana_cost <= 100);
ALTER TABLE ability ADD CONSTRAINT ability_lore_length CHECK (length(lore) <= 200);
ALTER TABLE ability ADD CONSTRAINT ability_description_length CHECK (length(description) <= 200);

-- Game run constraints
ALTER TABLE game_run ADD CONSTRAINT game_run_round_positive CHECK (current_round >= 1);

-- Row-Level Security
ALTER TABLE cat ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE ability ENABLE ROW LEVEL SECURITY;

-- Cat policies: users can only access their own cats
CREATE POLICY cat_select ON cat
    FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY cat_insert ON cat
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY cat_update ON cat
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY cat_delete ON cat
    FOR DELETE
    USING (user_id = auth.uid());

-- Game run policies: accessible via user_id
CREATE POLICY game_run_select ON game_run
    FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY game_run_insert ON game_run
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY game_run_update ON game_run
    FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY game_run_delete ON game_run
    FOR DELETE
    USING (user_id = auth.uid());

-- Ability policies: users can only access abilities for their own cats
CREATE POLICY ability_select ON ability
    FOR SELECT
    USING (
        creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())
    );

CREATE POLICY ability_insert ON ability
    FOR INSERT
    WITH CHECK (
        creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())
    );

CREATE POLICY ability_update ON ability
    FOR UPDATE
    USING (
        creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())
    )
    WITH CHECK (
        creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())
    );

CREATE POLICY ability_delete ON ability
    FOR DELETE
    USING (
        creature_id IN (SELECT id FROM cat WHERE user_id = auth.uid())
    );
