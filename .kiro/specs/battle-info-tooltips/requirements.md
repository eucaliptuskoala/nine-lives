# Requirements Document

## Introduction

The Battle screen (`BattlePage.tsx`, `BattleArena.tsx`, `ActionButtons.tsx`, `CatCard.tsx`) currently hides several pieces of information that already exist in the data returned by the Battle API. Players cannot easily see how many turns remain on an ability's cooldown, what an ability actually does, their own cat's underlying stats, the enemy's available abilities, or the enemy's stats. This feature adds purely informational, frontend-only UI (cooldown badges, hover/tap info panels) to the existing Battle screen. No backend changes are required: `GameState.player_ability_cooldowns`, `Enemy.abilities`, `Enemy.ability_cooldowns`, `CatResponse`, and `Ability`/`EnemyAbility` are already present in `BattleStateResponse` and `BattleActionResponse` (confirmed in `backend/models/schemas.py` and mirrored in `frontend/src/types/game.ts`). The enemy's current per-ability cooldown remaining (`Enemy.ability_cooldowns`) remains intentionally hidden from the player; only the player's own ability cooldowns are surfaced.

## Glossary

- **Battle_UI**: The collection of frontend components that render the Battle screen — `BattlePage`, `BattleArena`, `ActionButtons`, and `CatCard`.
- **Cooldown_Indicator**: A visually distinct badge rendered on a player ability button that shows the number of turns remaining before that ability can be used again, sourced from `GameState.player_ability_cooldowns`.
- **Ability_Info_Panel**: A tooltip-style panel that displays a single ability's name, description, damage value, effect (if any), and — for the player's own abilities only — lore.
- **Stat_Info_Panel**: A tooltip-style panel that displays a creature's (the player's cat or the enemy's) combat stats. A Stat_Info_Panel may be Pinned.
- **Pinned**: The state of a Stat_Info_Panel after a player pins it (see Requirement 5), causing it to remain visible when the pointer or focus that originally opened it moves away, until the player explicitly closes it.
- **Enemy_Ability_List**: An inline list of the enemy's ability names rendered on the enemy's `CatCard`.
- **Info_Icon**: A small icon control rendered on a Touch_Device that opens or closes an Ability_Info_Panel without triggering the underlying ability action.
- **Touch_Device**: A client whose primary pointer input does not support hover (detected via pointer/media capability, e.g. `(hover: none)`).
- **Player_Cat_Avatar**: The avatar image/element within the player's `CatCard` in the Battle screen.
- **Enemy_Avatar**: The avatar image/element within the enemy's `CatCard` in the Battle screen.

## Requirements

### Requirement 1: Player Ability Cooldown Visibility

**User Story:** As a player, I want to clearly see the cooldown remaining on each of my abilities, so that I can immediately tell which abilities are available to use.

#### Acceptance Criteria

1. WHILE an ability's remaining cooldown value in `player_ability_cooldowns` is greater than zero, THE Battle_UI SHALL render a Cooldown_Indicator on that ability's button showing the number of turns remaining.
2. WHILE an ability's remaining cooldown value in `player_ability_cooldowns` equals zero or the ability has no entry in `player_ability_cooldowns`, THE Battle_UI SHALL render the ability's button without a Cooldown_Indicator.
3. WHILE an ability's remaining cooldown value in `player_ability_cooldowns` is greater than zero, THE Battle_UI SHALL render that ability's button as disabled such that clicking, tapping, or activating it via keyboard does not submit the ability action.
4. WHEN an ability's remaining cooldown value transitions from greater than zero to zero, THE Battle_UI SHALL keep that ability's button disabled until the mana affordability and turn-phase conditions that separately govern the button's enabled state are satisfied.
5. WHEN a battle action response updates `player_ability_cooldowns`, THE Battle_UI SHALL update every Cooldown_Indicator to reflect the new values in the same render.
6. THE Cooldown_Indicator SHALL be rendered as a visual element separate from the ability's mana cost label, distinguished by a different icon, label text, or position on the button, such that the two can be identified as distinct elements without relying on color alone.

### Requirement 2: Player Ability Info Panel

**User Story:** As a player, I want to see an ability's effect, damage, and lore when I hover over it, so that I can decide which ability to use.

#### Acceptance Criteria

1. WHEN a player hovers a pointer over a player ability button, THE Battle_UI SHALL display an Ability_Info_Panel for that ability containing its description, damage value, effect, and lore.
2. WHEN the pointer leaves a player ability button, THE Battle_UI SHALL hide that ability's Ability_Info_Panel.
3. WHERE the client is a Touch_Device, THE Battle_UI SHALL render an Info_Icon on each player ability button.
4. WHEN a player taps the Info_Icon on a player ability button, THE Battle_UI SHALL toggle the visibility of that ability's Ability_Info_Panel.
5. WHEN a player taps an enabled player ability button outside its Info_Icon, THE Battle_UI SHALL submit that ability action without opening the Ability_Info_Panel; IF that tap simultaneously registers as an Info_Icon activation, THEN THE Battle_UI SHALL both submit the ability action and toggle the Ability_Info_Panel's visibility.
6. THE Ability_Info_Panel for a player ability SHALL source its content entirely from the ability data already present in `CatResponse.abilities`.
7. IF the `description` or `lore` field on a `CatResponse.abilities` entry is missing or an empty string, THEN THE Battle_UI SHALL render the panel with placeholder text for that field instead of omitting the panel.
8. THE Battle_UI SHALL treat an ability's `effect` field value of null as the valid state "no effect" and render it as such, distinct from the placeholder text used for a missing `description` or `lore`.
9. IF a player taps a disabled player ability button, whether on its Info_Icon or elsewhere on the button, THEN THE Battle_UI SHALL NOT submit that ability action and SHALL NOT change the visibility of that ability's Ability_Info_Panel.

### Requirement 3: Player Cat Stat Panel

**User Story:** As a player, I want to see my cat's stats when I hover over its sprite, so that I can understand my cat's combat capabilities.

#### Acceptance Criteria

1. WHEN a player hovers a pointer over the Player_Cat_Avatar, THE Battle_UI SHALL display a Stat_Info_Panel containing the player cat's damage, defence, speed, maximum HP, maximum mana, breed, and lore.
2. WHEN the pointer leaves the Player_Cat_Avatar, THE Battle_UI SHALL hide the Stat_Info_Panel.
3. WHERE the client is a Touch_Device, WHEN a player taps the Player_Cat_Avatar, THE Battle_UI SHALL toggle the visibility of the Stat_Info_Panel.
4. THE Stat_Info_Panel for the player's cat SHALL source its content entirely from the `CatResponse` object already returned by the Battle API.
5. IF the `breed` or `lore` field on the `CatResponse` object is missing or an empty string, THEN THE Battle_UI SHALL render the panel with placeholder text for that field instead of omitting the panel.

### Requirement 4: Enemy Ability List Without Cooldowns

**User Story:** As a player, I want to see which abilities the enemy has available, so that I can anticipate enemy actions, while the enemy's current cooldown status stays hidden as intended.

#### Acceptance Criteria

1. THE Battle_UI SHALL render an Enemy_Ability_List showing the name of each ability in `Enemy.abilities` on the enemy's `CatCard`.
2. THE Enemy_Ability_List SHALL present ability entries without any value from `Enemy.ability_cooldowns`.
3. WHEN a player hovers a pointer over an entry in the Enemy_Ability_List, THE Battle_UI SHALL display an Ability_Info_Panel for that ability containing its name, description, damage value, and effect.
4. IF the pointer leaves an entry in the Enemy_Ability_List and re-enters that same entry within 150 milliseconds, THEN THE Battle_UI SHALL keep that entry's Ability_Info_Panel visible without hiding it in the interim.
5. WHEN the pointer leaves an entry in the Enemy_Ability_List and does not re-enter that entry within 150 milliseconds, THE Battle_UI SHALL hide that entry's Ability_Info_Panel.
6. IF the pointer re-enters an entry in the Enemy_Ability_List after the 150 millisecond window in Acceptance Criterion 5 has elapsed, THEN THE Battle_UI SHALL treat it as a fresh hover and show that entry's Ability_Info_Panel again from a hidden state.
7. WHERE the client is a Touch_Device, THE Battle_UI SHALL render an Info_Icon on each Enemy_Ability_List entry.
8. WHERE the client is a Touch_Device, WHEN a player taps the Info_Icon on an Enemy_Ability_List entry, THE Battle_UI SHALL toggle the visibility of that ability's Ability_Info_Panel.

### Requirement 5: Enemy Stat Panel

**User Story:** As a player, I want to see the enemy's stats when I hover over it, so that I can gauge the threat it poses.

#### Acceptance Criteria

1. WHEN a player hovers a pointer over the Enemy_Avatar, THE Battle_UI SHALL display a Stat_Info_Panel containing the enemy's breed, attack, defence, speed, maximum HP, and maximum mana.
2. THE Battle_UI SHALL hide the Enemy_Avatar's Stat_Info_Panel when the pointer leaves the Enemy_Avatar, unless that Stat_Info_Panel is Pinned.
3. WHERE the client is not a Touch_Device, WHEN a player clicks the Enemy_Avatar while its Stat_Info_Panel is visible, THE Battle_UI SHALL set that Stat_Info_Panel to Pinned.
4. WHERE the client is not a Touch_Device, WHEN the Enemy_Avatar's Stat_Info_Panel is visible and has keyboard focus and a player presses Enter or Space, THE Battle_UI SHALL set that Stat_Info_Panel to Pinned.
5. THE Battle_UI SHALL keep a Pinned Stat_Info_Panel visible when the pointer or focus that opened it moves away.
6. WHEN a player clicks or taps a Pinned Stat_Info_Panel's close control, THE Battle_UI SHALL hide the Stat_Info_Panel and clear its Pinned state.
7. WHERE the client is a Touch_Device, WHEN a player taps the Enemy_Avatar, THE Battle_UI SHALL toggle the visibility of the Stat_Info_Panel.
8. THE Stat_Info_Panel for the enemy SHALL source its content entirely from the `Enemy` object already present in `GameState`.
9. THE Stat_Info_Panel for the enemy SHALL present only breed, attack, defence, speed, maximum HP, and maximum mana, omitting any value from `Enemy.ability_cooldowns`.
10. THE Battle_UI SHALL render a close control on every Pinned Stat_Info_Panel.

### Requirement 6: Accessible Focus Behavior for Info Panels

**User Story:** As a player using keyboard or assistive technology navigation, I want ability, cat, and enemy information available without relying on mouse hover or touch, so that I am not excluded from this information.

#### Acceptance Criteria

1. WHEN a player ability button, the Player_Cat_Avatar, the Enemy_Avatar, or an Enemy_Ability_List entry receives keyboard focus, THE Battle_UI SHALL display its associated Ability_Info_Panel or Stat_Info_Panel.
2. THE Battle_UI SHALL hide the panel associated with a player ability button, the Player_Cat_Avatar, the Enemy_Avatar, or an Enemy_Ability_List entry when keyboard focus moves away from that element, unless that panel is Pinned.
3. THE Battle_UI SHALL programmatically associate every Ability_Info_Panel and Stat_Info_Panel with its triggering element (via `aria-describedby` or an equivalent ARIA relationship) such that a screen reader announces the panel's text content when the triggering element receives focus.
4. WHERE the client is not a Touch_Device, WHEN the Enemy_Avatar's Stat_Info_Panel is visible via keyboard focus and a player presses Enter or Space, THE Battle_UI SHALL set that Stat_Info_Panel to Pinned, consistent with Requirement 5.

### Requirement 7: No New Backend Surface

**User Story:** As a developer, I want this feature built entirely on existing Battle API data, so that no new backend endpoints or schema changes are introduced for a UI-only feature.

#### Acceptance Criteria

1. THE Battle_UI SHALL derive all Cooldown_Indicator, Ability_Info_Panel, Stat_Info_Panel, and Enemy_Ability_List content exclusively from fields already present in `BattleStateResponse` and `BattleActionResponse` (`GameState`, `Enemy`, `EnemyAbility`, `Ability`, `CatResponse`).
2. THE Battle_UI SHALL NOT send a request to any Battle API endpoint other than the endpoints already used to start a battle and submit a battle action while implementing Requirements 1 through 6.
3. THE implementation of Requirements 1 through 6 SHALL NOT add, remove, rename, or change the data type of any field on `BattleStateResponse`, `BattleActionResponse`, `GameState`, `Enemy`, `EnemyAbility`, `Ability`, or `CatResponse`.
