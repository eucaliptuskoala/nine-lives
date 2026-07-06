# Requirements Document

## Introduction

Nine Lives is a cat digitization roguelike game that transforms user-uploaded cat photos into playable characters through machine learning and AI services. The game features turn-based combat with a 9-lives system, ability-based combat mechanics, and a memorial system for fallen cats.

The system follows a clear separation of concerns: the backend is the sole owner of all data access. Beyond being the authoritative game engine — owning all combat logic, enemy generation, state mutation, and persistence — the backend also mediates every database read and write. The frontend has no direct database access at all: it neither reads from nor writes to the database. The frontend uses the Supabase client solely for authentication (login, session management, and obtaining the JWT) and performs all data operations through authenticated backend HTTP endpoints. The frontend is a rendering and input layer — it displays data returned by the backend and submits player actions and data requests via authenticated backend endpoints.

This document specifies the functional requirements for the complete implementation including the cat digitization pipeline, the Battle API, the battle system, database integration, and memorial features.

## Glossary

- **System**: The Nine Lives game application (frontend + backend + database)
- **Digitization_Pipeline**: The backend process that transforms cat photos into game characters using ML/AI services
- **Battle_API**: The backend HTTP API that exposes battle actions to the frontend (`POST /api/battle/start`, `POST /api/battle/action`). All combat logic runs inside this API layer.
- **Data_API**: The backend HTTP API that mediates all non-battle, non-digitize database access for the frontend (`POST /api/game-runs`, `GET /api/cats/memorial`, `PATCH /api/cats/{cat_id}/note`). Each endpoint requires a valid Auth_Token, verifies it, and enforces ownership against the authenticated user. The frontend uses these endpoints instead of querying or writing the database directly.
- **Battle_System**: The authoritative turn-based combat engine running on the backend. It handles combat calculations, enemy generation, AI, state mutation, and persistence. The frontend never computes game outcomes directly.
- **Game_Run**: A single playthrough session from digitization through combat to memorial
- **Cat**: A playable character generated from a user's uploaded photo with stats, abilities, and lore
- **Enemy**: A procedurally generated opponent for combat encounters, created server-side by the Battle_System
- **Life**: One of 9 revival opportunities available to the player's cat
- **Ability**: A special combat action with mana cost, cooldown, and specific effects
- **Mana**: Resource used to cast abilities, regenerates each turn
- **Cooldown**: The number of turns before an ability can be used again
- **Memorial**: The final resting place displaying all cats that have exhausted their 9 lives
- **Game_State**: The complete, authoritative state of an active battle including HP, mana, cooldowns, phase, and enemy data. Owned and persisted exclusively by the Battle_System.
- **Phase**: The current turn indicator (PLAYER_TURN or ENEMY_TURN)
- **RLS**: Row Level Security policies that act as a defense-in-depth backstop at the database level. Primary data isolation is enforced by the backend API layer using the authenticated user's identity.
- **Auth_Token**: A valid Supabase JWT that the frontend includes in every backend data and battle request. The frontend obtains the Auth_Token from the Supabase client, which it uses for authentication only. The backend verifies the token and confirms the user owns the requested resource before processing any operation.
- **HomePage**: The public frontend landing page served at the `/` route. It adapts its content to the authentication state and never forces a redirect.
- **BattlePage**: The protected frontend combat page served at the `/battle/{run_id}` route that renders the Game_State returned by the Battle_API.
- **OverworldPage**: The protected frontend hub page served at the `/overworld` route, reached after the player wins a round, from which the player chooses where to go next.
- **Active_Run**: A game_run with status IN_PROGRESS whose associated Cat has status ALIVE, as returned by the `GET /api/game-runs/active` endpoint.

## Requirements

### Requirement 1: Cat Digitization Inputs

**User Story:** As a user, I want to provide my cat's name, a photo, and an optional personality description, so that I can transform it into a personalized playable character.

**Context (non-normative):** The DigitizePage collects three inputs — the cat name (required), the cat photo (required), and an optional personality description that gives the card-generation LLM additional context. The "no name / generic cat" case (digitizing without a user-provided name) is explicitly out of scope and reserved for future work.

#### Acceptance Criteria

1. WHEN a user selects an image file, THE System SHALL accept files in JPEG, PNG, or WebP format
2. WHEN a user selects a file larger than 10MB, THE System SHALL reject the upload and display an error message
3. WHEN a user uploads a valid file, THE frontend SHALL call the `POST /api/game-runs` endpoint with a valid Auth_Token, and THE Data_API SHALL create a game_run record with status DIGITIZING and return its run_id
4. WHEN an upload fails, THE System SHALL display an error message and allow the user to retry
5. WHEN a user provides a cat name, THE System SHALL require a non-empty name of at most 100 characters
6. WHERE a user provides an optional personality description, THE System SHALL accept a description of at most 500 characters
7. IF the cat name is empty or exceeds 100 characters, THEN THE System SHALL display a validation error and SHALL disable submission
8. IF the personality description exceeds 500 characters, THEN THE System SHALL display a validation error
9. WHEN the user submits the digitization form, THE frontend SHALL pass the cat name and the optional personality description to `POST /api/digitize` along with the photo

### Requirement 2: Breed Classification

**User Story:** As a user, I want the system to identify my cat's breed, so that the character is personalized to my cat.

#### Acceptance Criteria

1. WHEN a valid cat photo is provided, THE Digitization_Pipeline SHALL run a local, in-process HuggingFace `transformers` image-classification model (`dima806/cat_breed_image_detection`, a fine-tuned ViT) to classify the breed
2. WHEN the breed classification succeeds, THE Digitization_Pipeline SHALL return a breed name
3. IF the breed classification fails, THEN THE Digitization_Pipeline SHALL use a fallback default breed value

### Requirement 3: Color Extraction

**User Story:** As a user, I want the system to extract my cat's fur colors, so that the character reflects my cat's appearance.

#### Acceptance Criteria

1. WHEN a valid cat photo is provided, THE Digitization_Pipeline SHALL first segment the cat from the photo using YOLO instance segmentation (`yolo11s-seg.pt`, COCO class 15 = cat) to exclude background pixels, and then extract the 5 dominant colors from the cat pixels using scikit-learn KMeans with 5 clusters
2. WHEN color extraction completes, THE Digitization_Pipeline SHALL return each color as a hex code string together with its per-color pixel ratio, defined as the fraction of cat pixels assigned to that color cluster
3. WHEN color extraction fails, THE Digitization_Pipeline SHALL retry the extraction step up to 3 times
4. WHEN color extraction completes, THE Digitization_Pipeline SHALL provide the extracted color and per-color ratio data to the card-generation step so that color dominance informs card generation

### Requirement 4: Character Card Generation

**User Story:** As a user, I want the system to generate unique stats and abilities for my cat, so that each character is distinct and interesting to play.

#### Acceptance Criteria

1. WHEN breed and color data are available, THE Digitization_Pipeline SHALL call the Gemini API to generate character stats
2. WHEN card generation completes, THE Digitization_Pipeline SHALL return a name, class, max HP, damage, defence, speed, max mana, 4 abilities, lore text, and an image prompt
3. THE Digitization_Pipeline SHALL generate exactly 3 regular abilities and 1 special ability per cat
4. WHEN generating abilities, THE Digitization_Pipeline SHALL assign mana costs between 0 and 100
5. WHEN generating abilities, THE Digitization_Pipeline SHALL assign cooldowns between 0 and 5 turns
6. WHEN generating stats, THE Digitization_Pipeline SHALL ensure max HP is between 30 and 200
7. WHEN generating stats, THE Digitization_Pipeline SHALL ensure damage is between 5 and 50
8. WHEN generating stats, THE Digitization_Pipeline SHALL ensure defence is between 3 and 40
9. WHEN generating stats, THE Digitization_Pipeline SHALL ensure speed is between 5 and 50
10. WHEN generating stats, THE Digitization_Pipeline SHALL ensure max mana is between 50 and 200
11. WHEN a personality description is provided, THE Digitization_Pipeline SHALL incorporate the personality description into the Gemini 2.5 Flash prompt as context influencing the generated class, stats, abilities, and lore
12. WHERE no personality description is provided, THE Digitization_Pipeline SHALL generate the character card from the breed and colors alone
13. WHEN generating the character card, THE Digitization_Pipeline SHALL provide the cat name, breed, and the color and per-color ratio data to the Gemini 2.5 Flash card generator as inputs

### Requirement 5: Avatar Image Generation

**User Story:** As a user, I want the system to generate a stylized avatar for my cat in a consistent retro pixel-art style, so that my character has a unique visual representation that fits the retro 8-bit interface.

**Context (non-normative):** The per-cat subject (breed, colors, class, personality) varies for each avatar, while the retro pixel-art style block is constant. Applying the same canonical style to every avatar keeps the digitized cats visually cohesive with the 8-bit (8bitcn) user interface.

#### Acceptance Criteria

1. WHEN an image prompt is available, THE Digitization_Pipeline SHALL generate an avatar image using FLUX.1-schnell via HuggingFace Inference Providers (fal.ai)
2. WHEN avatar generation completes, THE Digitization_Pipeline SHALL upload the image to Supabase storage
3. WHEN the upload completes, THE Digitization_Pipeline SHALL return a public URL for the avatar
4. WHEN generating a cat avatar, THE Digitization_Pipeline SHALL apply the canonical retro pixel-art style defined in `docs/retro-avatar-prompt.md` to the per-cat image prompt, expressing both the desired retro pixel-art style and the terms to avoid within a single positive prompt, because FLUX.1-schnell is guidance-free and provides no negative-prompt field, so that all generated avatars are visually consistent with the retro 8-bit user interface

### Requirement 6: Cat Record Persistence

**User Story:** As a user, I want my digitized cat to be saved, so that I can play with it in battles.

#### Acceptance Criteria

1. WHEN all digitization steps complete successfully, THE Digitization_Pipeline SHALL create a cat record in the database
2. WHEN creating a cat record, THE Digitization_Pipeline SHALL store the user_id, breed, name, class, stats, abilities, lore, source image URL, avatar URL, and personality description
3. WHEN a cat is created, THE System SHALL set the cat status to ALIVE
4. WHEN a cat is created, THE System SHALL set lives_remaining to 9
5. WHEN a cat is created, THE System SHALL update the game_run record with the cat_id
6. WHEN a cat is created, THE System SHALL set the game_run status to IN_PROGRESS
7. WHERE a personality description is provided, THE Digitization_Pipeline SHALL persist the user-provided personality description on the cat record

### Requirement 7: Battle Initialization

**User Story:** As a user, I want to start battling immediately after digitization, so that I can begin playing the game.

#### Acceptance Criteria

1. WHEN digitization completes, THE System SHALL navigate the user to the Battle Page
2. WHEN the Battle Page loads, THE frontend SHALL call `POST /api/battle/start` with the run_id and a valid Auth_Token
3. WHEN `POST /api/battle/start` is received, THE Battle_API SHALL verify the Auth_Token and confirm the user owns the game_run
4. WHEN authorization succeeds, THE Battle_API SHALL load the cat and its abilities from the database
5. WHEN battle data loads successfully, THE Battle_System SHALL create a new Game_State with: player HP set to cat max HP, player mana set to cat max mana, current_round set to 1, phase set to PLAYER_TURN, and all player special ability cooldowns set to their maximum cooldown values to prevent first-turn ultimate usage
6. WHEN the Game_State is created, THE Battle_System SHALL generate an enemy for round 1 server-side and include it in the Game_State
7. WHEN the Game_State is fully initialized, THE Battle_System SHALL persist it to game_run.state in the database
8. WHEN persistence succeeds, THE Battle_API SHALL return the complete initial Game_State to the frontend
9. WHEN the Battle Page receives the Game_State response, THE frontend SHALL render the battle scene from the returned state without performing any combat calculations
10. IF a game_run already has a persisted Game_State, THEN THE Battle_API SHALL return the existing state instead of creating a new one
11. WHEN the Battle_API returns the initial Game_State from `POST /api/battle/start`, THE Battle_API SHALL include the player Cat data (name, class, stats, avatar, and abilities) in the response payload so the frontend can render the player's identity and ability list
12. THE Battle_API SHALL include the player Cat in the `POST /api/battle/start` response payload only and SHALL exclude the Cat from game_run.state, because the Cat is static data and not part of the persisted Game_State

### Requirement 8: Enemy Generation

**User Story:** As a user, I want to face increasingly difficult enemies as I progress, so that the game remains challenging.

#### Acceptance Criteria

1. WHEN the Battle_System generates an enemy for a given round, THE Battle_System SHALL calculate a multiplier as 1 + (round - 1) * 0.3
2. WHEN calculating enemy HP, THE Battle_System SHALL use the formula floor((20 + round * 5) * multiplier)
3. WHEN calculating enemy attack, THE Battle_System SHALL use the formula floor((8 + round * 2) * multiplier)
4. WHEN calculating enemy defence, THE Battle_System SHALL use the formula floor((6 + round * 1.5) * multiplier)
5. WHEN calculating enemy speed, THE Battle_System SHALL use the formula floor((7 + round * 2) * multiplier)
6. WHEN calculating enemy max mana, THE Battle_System SHALL use the formula 80 + round * 5
7. WHEN an enemy is generated, THE Battle_System SHALL set starting mana to 60% of max mana
8. WHEN an enemy is generated, THE Battle_System SHALL assign exactly 4 abilities (3 regular + 1 special) selected server-side from the enemy ability pool
9. WHEN a new enemy is generated, THE Battle_System SHALL set the special ability cooldown to its maximum cooldown value to prevent immediate ultimate usage
10. THE frontend SHALL NOT generate or compute enemy data; enemy data is always supplied by the Battle_API response

### Requirement 9: Basic Attack

**User Story:** As a user, I want to perform basic attacks against enemies, so that I can deal damage without using mana.

#### Acceptance Criteria

1. WHEN the frontend submits `POST /api/battle/action` with `action: "attack"`, THE Battle_API SHALL verify the Auth_Token and confirm the user owns the game_run
2. WHEN authorization succeeds and the current Game_State phase is PLAYER_TURN, THE Battle_System SHALL calculate damage as max(player_dmg - enemy_defence * 0.5, 1)
3. WHEN attack damage is calculated, THE Battle_System SHALL ensure damage is at least 1
4. WHEN attack damage is calculated, THE Battle_System SHALL subtract the damage from enemy HP
5. WHEN the player attack resolves, THE Battle_System SHALL immediately resolve the enemy turn (see Requirement 15) before responding
6. WHEN the full turn resolves, THE Battle_System SHALL persist the updated Game_State and return it to the frontend
7. THE frontend SHALL NOT compute attack damage; it SHALL only render the Game_State returned by the Battle_API
8. WHEN the Battle_API returns a `POST /api/battle/action` response for any action type (attack, defend, or ability), THE Battle_API SHALL include the player Cat data (name, class, stats, avatar, and abilities) in the response payload alongside the Game_State, game_over flag, revival flag, and events, so the frontend can render the player's identity and ability list
9. THE Battle_API SHALL include the player Cat in the `POST /api/battle/action` response payload only and SHALL exclude the Cat from game_run.state, consistent with the Battle_System being the sole writer of Game_State, because the Cat is static data and not part of the persisted Game_State

### Requirement 10: Defend Action

**User Story:** As a user, I want to defend to reduce incoming damage, so that I can survive powerful enemy attacks.

#### Acceptance Criteria

1. WHEN the frontend submits `POST /api/battle/action` with `action: "defend"`, THE Battle_API SHALL verify the Auth_Token and confirm the user owns the game_run
2. WHEN authorization succeeds and the current Game_State phase is PLAYER_TURN, THE Battle_System SHALL set player_is_defending to true
3. WHEN the player is defending and receives damage, THE Battle_System SHALL reduce incoming damage by 50%
4. WHEN the player's turn begins, THE Battle_System SHALL reset player_is_defending to false
5. WHEN the defend action resolves, THE Battle_System SHALL immediately resolve the enemy turn (see Requirement 15) before responding
6. WHEN the full turn resolves, THE Battle_System SHALL persist the updated Game_State and return it to the frontend

### Requirement 11: Ability Usage

**User Story:** As a user, I want to use special abilities with unique effects, so that I have strategic options in combat.

#### Acceptance Criteria

1. WHEN the frontend submits `POST /api/battle/action` with `action: "ability"` and an `ability_id`, THE Battle_API SHALL verify the Auth_Token and confirm the user owns the game_run
2. WHEN authorization succeeds and the current Game_State phase is PLAYER_TURN, THE Battle_System SHALL check if player mana is greater than or equal to the ability mana cost
3. WHEN checking ability availability, THE Battle_System SHALL verify the ability cooldown is 0
4. WHEN an ability is used, THE Battle_System SHALL subtract the mana cost from player mana
5. WHEN an ability is used, THE Battle_System SHALL set the ability cooldown to its maximum cooldown value
6. WHEN an ability of type DMG is used, THE Battle_System SHALL apply the ability damage to the target ignoring the target's defence, with the target's shield absorbing the damage before it reaches HP
7. WHEN an ability of type HEAL is used, THE Battle_System SHALL increase player HP by the ability value without exceeding max HP
8. WHEN an ability of type SHIELD is used, THE Battle_System SHALL add the ability value to player_shield
9. IF player mana is less than the ability cost or cooldown is greater than 0, THEN THE Battle_System SHALL reject the action and return an error response without modifying Game_State
10. WHEN the ability action resolves, THE Battle_System SHALL immediately resolve the enemy turn (see Requirement 15) before responding
11. WHEN the full turn resolves, THE Battle_System SHALL persist the updated Game_State and return it to the frontend

### Requirement 12: Mana Regeneration

**User Story:** As a user, I want mana to regenerate each turn, so that I can continue using abilities throughout the battle.

#### Acceptance Criteria

1. WHEN a player turn begins (before processing the player action), THE Battle_System SHALL increase player mana by floor(player_max_mana * 0.1)
2. WHEN mana is regenerated, THE Battle_System SHALL ensure player mana does not exceed max mana
3. WHEN the enemy turn begins, THE Battle_System SHALL increase enemy mana by floor(enemy_max_mana * 0.1)
4. WHEN enemy mana is regenerated, THE Battle_System SHALL ensure enemy mana does not exceed max mana

### Requirement 13: Cooldown Management

**User Story:** As a user, I want ability cooldowns to decrease each turn, so that I can use my abilities again after waiting.

#### Acceptance Criteria

1. WHEN a player turn begins (before processing the player action), THE Battle_System SHALL decrement all player ability cooldowns by 1 for cooldowns greater than 0
2. WHEN a cooldown reaches 0, THE Battle_System SHALL make the ability available for use
3. WHEN the enemy turn begins, THE Battle_System SHALL decrement all enemy ability cooldowns by 1 for cooldowns greater than 0

### Requirement 14: Shield Mechanics

**User Story:** As a user, I want shields to absorb damage before affecting HP for both my cat and the enemy, so that shield abilities provide meaningful protection on both sides symmetrically.

#### Acceptance Criteria

1. WHEN incoming damage is applied to the player, THE Battle_System SHALL first subtract damage from player_shield
2. WHEN player_shield is greater than or equal to incoming damage, THE Battle_System SHALL reduce shield by the full damage amount and apply 0 damage to HP
3. WHEN player_shield is less than incoming damage, THE Battle_System SHALL reduce shield to 0 and apply the remaining damage to HP
4. WHEN the player is defending and has a shield, THE Battle_System SHALL apply the defend reduction before shield absorption
5. WHEN incoming damage is applied to the enemy, THE Battle_System SHALL first subtract damage from the enemy's shield, then apply the remaining damage to enemy HP, mirroring the player shield behavior
6. WHEN the enemy's shield is greater than or equal to incoming damage, THE Battle_System SHALL reduce the enemy's shield by the full damage amount and apply 0 damage to enemy HP
7. WHEN the enemy's shield is less than incoming damage, THE Battle_System SHALL reduce the enemy's shield to 0 and apply the remaining damage to enemy HP
8. WHEN damage reaches the enemy from a basic attack or from a DMG or TRUE_DMG ability, THE Battle_System SHALL apply the enemy's shield absorption before enemy HP

### Requirement 15: Enemy AI Turn

**User Story:** As a user, I want enemies to take intelligent actions, so that combat is challenging and engaging.

#### Acceptance Criteria

1. WHEN a player action (attack, defend, or ability) resolves, THE Battle_System SHALL automatically resolve the enemy turn server-side without any separate frontend trigger
2. WHEN resolving the enemy turn, THE Battle_System SHALL first regenerate enemy mana and tick enemy cooldowns
3. WHEN the enemy has sufficient mana and an available ability (cooldown = 0), THE Battle_System SHALL prioritize using the special (ultimate) ability if available, otherwise select randomly from available regular abilities
4. WHEN no ability is available, THE Battle_System SHALL fall back to a basic attack
5. WHEN the enemy uses an ability, THE Battle_System SHALL follow the same rules as player ability usage (mana cost, cooldown, effect application), including adding the ability value to the enemy's shield when the ability is of type SHIELD
6. WHEN the enemy uses a basic attack, THE Battle_System SHALL calculate damage using the formula max(enemy_atk - player_defence * 0.5, 1)
7. WHEN the enemy action completes, THE Battle_System SHALL resolve any death/revival logic (see Requirement 17) and include the final Game_State in the Battle_API response

### Requirement 16: HP Bounds

**User Story:** As a user, I want HP to stay within valid bounds, so that the game state remains consistent.

#### Acceptance Criteria

1. THE Battle_System SHALL ensure player HP is always between 0 and max HP
2. THE Battle_System SHALL ensure enemy HP is always between 0 and max HP
3. WHEN healing is applied, THE Battle_System SHALL prevent HP from exceeding max HP

### Requirement 17: Death and Revival

**User Story:** As a user, I want my cat to revive when it dies, so that I can continue playing with my 9 lives.

#### Acceptance Criteria

1. WHEN player HP reaches 0 and lives_remaining is greater than 0, THE Battle_System SHALL decrement lives_remaining by 1
2. WHEN a life is lost, THE Battle_System SHALL restore player HP to max HP
3. WHEN a life is lost, THE Battle_System SHALL restore player mana to max mana
4. WHEN a life is lost, THE Battle_System SHALL reset player_shield to 0
5. WHEN a life is lost, THE Battle_System SHALL include a revival event in the Game_State response so the frontend can display a revival notification

### Requirement 18: Game Over

**User Story:** As a user, I want the game to end when I run out of lives, so that I can see my cat's final memorial.

#### Acceptance Criteria

1. WHEN player HP reaches 0 and lives_remaining equals 0, THE Battle_System SHALL set the cat status to MEMORIAL
2. WHEN the cat status is set to MEMORIAL, THE Battle_System SHALL set the game_run status to COMPLETED
3. WHEN the game ends, THE Battle_System SHALL set the cat death_date to the current timestamp
4. WHEN the game ends, THE Battle_API SHALL return a Game_State response with a game_over flag so the frontend can navigate the user to the Memorial Page

### Requirement 19: Enemy Defeat and Round Progression

**User Story:** As a user, I want to progress to the next round when I defeat an enemy, so that I can continue playing and face stronger opponents.

#### Acceptance Criteria

1. WHEN enemy HP reaches 0, THE Battle_System SHALL increment the cat wins counter by 1
2. WHEN enemy HP reaches 0, THE Battle_System SHALL increment current_round by 1
3. WHEN a new round begins, THE Battle_System SHALL generate a new enemy server-side scaled to the new round number
4. WHEN a new round begins, THE Battle_System SHALL maintain player HP, mana, and cooldowns from the previous round
5. WHEN a new round begins, THE Battle_System SHALL skip the enemy turn for that action and set phase to PLAYER_TURN

### Requirement 20: State Persistence

**User Story:** As a user, I want the game to save my progress automatically, so that I can continue playing even if I close the browser.

#### Acceptance Criteria

1. WHEN any Battle_API action resolves (player action + enemy turn complete), THE Battle_System SHALL persist the full updated Game_State to game_run.state in the database before sending the response
2. THE frontend SHALL NOT write to game_run.state directly; the Battle_System is the sole writer of game state to the database
3. WHEN the Battle Page loads an existing game_run, THE frontend SHALL call `POST /api/battle/start` to retrieve the persisted Game_State from the backend
4. WHEN state persistence fails, THE Battle_System SHALL log the error and return an error response; the frontend SHALL display a persistence error message and allow the user to retry the action
5. WHEN the Battle_API receives an action for a game_run that has status COMPLETED, THE Battle_API SHALL reject the action with a 409 Conflict response

### Requirement 21: Battle API Authentication and Authorization

**User Story:** As a user, I want my battle session to be protected, so that other users cannot submit actions on my behalf.

#### Acceptance Criteria

1. WHEN any request is made to `POST /api/battle/start` or `POST /api/battle/action`, THE Battle_API SHALL require a valid Auth_Token in the request Authorization header
2. WHEN the Auth_Token is missing or invalid, THE Battle_API SHALL return a 401 Unauthorized response
3. WHEN a valid Auth_Token is present, THE Battle_API SHALL verify that the game_run identified by run_id belongs to the authenticated user
4. WHEN the game_run does not belong to the authenticated user, THE Battle_API SHALL return a 403 Forbidden response
5. THE Battle_API SHALL never process a battle action without first completing both authentication and ownership verification

### Requirement 22: Memorial Display

**User Story:** As a user, I want to view all my fallen cats in a memorial, so that I can remember my past playthroughs.

#### Acceptance Criteria

1. WHEN the Memorial Page loads, THE frontend SHALL call the `GET /api/cats/memorial` endpoint with a valid Auth_Token to retrieve the cats, and THE Data_API SHALL return all cats with status MEMORIAL that belong to the authenticated user
2. WHEN memorial cats are returned, THE System SHALL display each cat's name, breed, class, stats, abilities, lore, and avatar
3. WHEN memorial cats are returned, THE System SHALL display the death_date for each cat
4. WHEN memorial cats are returned, THE System SHALL display the wins counter for each cat
5. WHEN memorial cats are returned, THE System SHALL display the personal_note if one exists
6. THE frontend SHALL NOT query the database directly for memorial cats; memorial data is always supplied by the Data_API response

### Requirement 23: Personal Notes

**User Story:** As a user, I want to add personal notes to my fallen cats, so that I can record memories about each playthrough.

#### Acceptance Criteria

1. WHEN viewing a cat in the memorial, THE System SHALL provide an interface to add or edit a personal note
2. WHEN a user saves a personal note, THE frontend SHALL call the `PATCH /api/cats/{cat_id}/note` endpoint with a valid Auth_Token, and THE Data_API SHALL verify the authenticated user owns the cat and update the cat record with the note text
3. IF the authenticated user does not own the cat identified by cat_id, THEN THE Data_API SHALL reject the update with a 403 Forbidden response
4. IF a personal note exceeds 500 characters, THEN THE Data_API SHALL reject the update with an error response, and THE frontend SHALL display an error message
5. THE frontend SHALL NOT update the cat record in the database directly; note updates are always performed by the Data_API

### Requirement 24: Data Isolation

**User Story:** As a user, I want my cat data to be private, so that other users cannot access my cats.

#### Acceptance Criteria

1. WHEN the frontend requests cats through the Data_API, THE Data_API SHALL only return cats where the user_id matches the authenticated user's ID extracted from the verified Auth_Token
2. WHEN a request targets a cat or game_run that does not belong to the authenticated user, THE backend API layer SHALL deny access by returning a 403 Forbidden response
3. WHEN the frontend requests game_runs through the backend, THE backend SHALL only return game_runs associated with the authenticated user's cats
4. THE backend API layer SHALL be the primary enforcement point for data isolation, verifying resource ownership against the authenticated user before any read or write
5. THE System SHALL configure RLS policies as a defense-in-depth backstop at the database level
6. WHEN the frontend requests `GET /api/game-runs/active` with a valid Auth_Token, THE Data_API SHALL return the authenticated user's most recent IN_PROGRESS game_run whose Cat has status ALIVE as `{ run_id, cat }`, enforcing ownership by user_id
7. IF the authenticated user has no Active_Run, THEN THE Data_API SHALL return `{ run_id: null, cat: null }`

### Requirement 25: Authentication

**User Story:** As a user, I want to authenticate securely, so that my data is protected.

#### Acceptance Criteria

1. WHERE a route is the HomePage (`/`) or the Login Page (`/login`), THE System SHALL render the route publicly without requiring an authentication token
2. WHEN a user accesses the Digitize Page at `/digitize`, THE System SHALL verify the user has a valid authentication token
3. WHEN a user accesses the BattlePage, THE System SHALL verify the user has a valid authentication token
4. WHEN a user accesses the Memorial Page, THE System SHALL verify the user has a valid authentication token
5. WHEN a user accesses the OverworldPage, THE System SHALL verify the user has a valid authentication token
6. IF the authentication token is invalid or expired, THEN THE System SHALL redirect the user to the login page

### Requirement 26: Error Recovery

**User Story:** As a user, I want clear error messages when something goes wrong, so that I know how to proceed.

#### Acceptance Criteria

1. WHEN any API call fails, THE System SHALL display a user-friendly error message
2. WHEN a digitization error occurs, THE System SHALL allow the user to retry the upload
3. WHEN a Battle_API action returns an error, THE frontend SHALL display the error and re-enable the action buttons so the user can retry
4. WHEN a network timeout occurs after 30 seconds, THE System SHALL display a timeout message and offer a retry option

### Requirement 27: Image Validation

**User Story:** As a user, I want to be notified immediately if my uploaded image is invalid, so that I don't waste time waiting for processing.

#### Acceptance Criteria

1. WHEN a user selects an image file, THE System SHALL validate the file extension is .jpg, .jpeg, .png, or .webp
2. WHEN a user selects an image file, THE System SHALL validate the file size is 10MB or less
3. IF validation fails, THEN THE System SHALL display a specific error message explaining the validation failure
4. IF validation succeeds, THEN THE System SHALL enable the upload button

### Requirement 28: Combat Formula Consistency

**User Story:** As a developer, I want combat calculations to be deterministic and consistent, so that the game behaves predictably.

#### Acceptance Criteria

1. THE Battle_System SHALL always calculate basic attack damage as max(attacker_dmg - defender_defence * 0.5, 1)
2. THE Battle_System SHALL always guarantee at least 1 damage from basic attacks
3. WHEN defend is active, THE Battle_System SHALL always reduce incoming damage by exactly 50%
4. WHEN abilities deal damage, THE Battle_System SHALL apply the ability damage bypassing the target's defence reduction, while the target's shield still absorbs the damage before it reaches HP
5. ALL combat calculations SHALL occur on the backend; the frontend SHALL treat Game_State values as the authoritative source of truth

### Requirement 29: State Validation

**User Story:** As a developer, I want game state to be validated when loaded, so that corrupted data doesn't crash the game.

#### Acceptance Criteria

1. WHEN the Battle_System loads a Game_State from the database, THE Battle_System SHALL verify player_hp is between 0 and player_max_hp
2. WHEN the Battle_System loads a Game_State from the database, THE Battle_System SHALL verify player_mana is between 0 and player_max_mana
3. WHEN the Battle_System loads a Game_State from the database, THE Battle_System SHALL verify lives_remaining is between 0 and 9
4. WHEN the Battle_System loads a Game_State from the database, THE Battle_System SHALL verify phase is either PLAYER_TURN or ENEMY_TURN
5. IF any validation fails, THEN THE Battle_System SHALL return an error response to the frontend; the frontend SHALL display the error and prevent battle actions

### Requirement 30: Digitization Pipeline Serialization

**User Story:** As a developer, I want the digitization pipeline to properly serialize cat data, so that it can be stored in and retrieved from the database correctly.

#### Acceptance Criteria

1. WHEN the Digitization_Pipeline creates a cat record, THE System SHALL serialize all cat properties to JSON
2. WHEN the Battle_System loads a cat from the database, THE System SHALL deserialize JSON back into a valid Cat object
3. FOR ALL valid Cat objects, serializing then deserializing SHALL produce an equivalent object

### Requirement 31: Ability Data Integrity

**User Story:** As a developer, I want ability data to maintain integrity, so that each cat always has the correct number of abilities.

#### Acceptance Criteria

1. THE Digitization_Pipeline SHALL ensure each cat has exactly 4 abilities
2. THE Digitization_Pipeline SHALL ensure exactly 1 ability has is_special set to true
3. WHEN the Battle_System loads a cat from the database, THE Battle_System SHALL verify the cat has exactly 4 abilities
4. IF ability validation fails, THEN THE Battle_System SHALL return an error response and prevent battle actions

### Requirement 32: Home / Landing Page

**User Story:** As a user, I want a landing page, so that I can sign in or jump straight into playing.

#### Acceptance Criteria

1. THE System SHALL serve the `/` route publicly, rendered without the authentication guard
2. THE HomePage SHALL display the game title "Nine Lives"
3. WHEN the user is not authenticated, THE HomePage SHALL display a tagline and a "Sign In" control that navigates to `/login`
4. WHEN the user is authenticated, THE HomePage SHALL display an intro and navigation controls labeled "New Game" that navigates to `/digitize` and "Memorial" that navigates to `/memorial`
5. WHEN the authenticated user has an Active_Run, THE HomePage SHALL display a "Continue" control that navigates to `/battle/{run_id}`
6. THE HomePage SHALL determine Active_Run status via the backend `GET /api/game-runs/active` endpoint rather than a direct database query

### Requirement 33: Overworld Hub

**User Story:** As a user, I want a hub after winning a battle, so that I can choose what to do next.

**Context (non-normative):** The victory-to-Overworld transition is a frontend navigation change only. The Battle_System already advances the round and generates the next enemy within the same `POST /api/battle/action` response when the enemy is defeated (see Requirement 19); no combat or round mechanics change as a result of this requirement.

#### Acceptance Criteria

1. THE System SHALL protect the `/overworld` route with the authentication guard, requiring a valid authentication token
2. WHEN the player defeats the enemy in a round, THE BattlePage SHALL display a dismissible victory popup
3. WHEN the player dismisses the victory popup, THE System SHALL navigate to `/overworld`
4. THE OverworldPage SHALL present a "Next Enemy" navigation node that navigates to `/battle/{run_id}`, resuming the current run
5. THE OverworldPage SHALL present a "Memorial" navigation node that navigates to `/memorial`
6. WHERE a "Rest" placeholder node is provided, THE OverworldPage SHALL render it as a disabled node
7. THE OverworldPage SHALL resolve the current `run_id` via the backend `GET /api/game-runs/active` endpoint so that navigation works after a page refresh
8. THE OverworldPage SHALL display a fullscreen background image sourced from the frontend assets folder
