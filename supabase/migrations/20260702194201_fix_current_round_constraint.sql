ALTER TABLE game_run DROP CONSTRAINT IF EXISTS game_run_round_positive;
ALTER TABLE game_run ADD CONSTRAINT game_run_round_non_negative CHECK (current_round >= 0);
