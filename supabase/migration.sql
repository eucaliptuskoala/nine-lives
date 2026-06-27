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
CREATE INDEX idx_game_run_cat_id ON game_run(cat_id);
CREATE INDEX idx_ability_creature_id ON ability(creature_id);

-- Row-Level Security
ALTER TABLE cat ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE ability ENABLE ROW LEVEL SECURITY;

-- Cat: users can CRUD their own cats
CREATE POLICY cat_owner ON cat
    FOR ALL
    USING (user_id = auth.uid());

-- Game run: accessible via cat owner
CREATE POLICY game_run_owner ON game_run
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM cat WHERE cat.id = game_run.cat_id AND cat.user_id = auth.uid()
        )
    );

-- Ability: accessible via cat owner
CREATE POLICY ability_owner ON ability
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM cat WHERE cat.id = ability.creature_id AND cat.user_id = auth.uid()
        )
    );
