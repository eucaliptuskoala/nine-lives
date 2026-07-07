# Implementation Plan: Battle Info Tooltips

## Overview

This plan builds the feature bottom-up: the pure derivation module and the shared
disclosure hook first (both fully property-tested in isolation, no React rendering
required), then the small presentational panel/icon components, then the wiring into
`ActionButtons`, `CatCard`, `BattleArena`, and `BattlePage`. Accessibility behavior
(Requirement 6) is not a separate bolt-on task — it is implemented as part of the
`useInfoDisclosure` hook (focus/blur, Enter/Space-to-pin, `aria-describedby`) and
verified as part of each wiring task's tests. No backend changes are made anywhere in
this plan (Requirement 7).

Implementation language: TypeScript / React (existing `frontend` project conventions).

## Tasks

- [x] 1. Add `fast-check` as a new frontend dev dependency
  - [x] 1.1 Run `npm install -D fast-check` in `frontend/` and verify it resolves under the existing Vitest setup
    - _Requirements: 7.1_

- [x] 2. Implement `frontend/src/lib/battleInfo.ts` — pure derivation module
  - [x] 2.1 Implement placeholder/effect helpers and field projection functions
    - `PLACEHOLDER_TEXT`, `NO_EFFECT_TEXT` constants; `withPlaceholder`, `formatEffect`
    - `getAbilityInfoFields(ability: Ability)`, `getEnemyAbilityInfoFields(ability: EnemyAbility)`
    - `getPlayerStatFields(cat: Cat)`, `getEnemyStatFields(enemy: Enemy)`
    - `toEnemyAbilityList(enemy: Enemy)` (id + name only, in `enemy.abilities` order)
    - _Requirements: 2.6, 2.7, 2.8, 3.4, 3.5, 4.1, 4.2, 4.3, 5.1, 5.8, 5.9, 7.1, 7.3_

  - [x] 2.2 Write property test for player ability info projection
    - **Property 6: Player ability info content is a faithful, placeholder-safe projection**
    - **Validates: Requirements 2.6, 2.7, 2.8**

  - [x] 2.3 Write property test for enemy ability info projection
    - **Property 7: Enemy ability info content is a faithful, placeholder-safe projection**
    - **Validates: Requirements 4.3**

  - [x] 2.4 Write property test for player stat panel projection
    - **Property 8: Player stat panel content is a faithful, placeholder-safe projection**
    - **Validates: Requirements 3.4, 3.5**

  - [x] 2.5 Write property test for enemy stat panel projection
    - **Property 9: Enemy stat panel content excludes cooldowns and contains exactly six fields**
    - **Validates: Requirements 5.1, 5.8, 5.9**

  - [x] 2.6 Write property test for enemy ability list projection
    - **Property 10: Enemy ability list entries preserve order and identity, and never leak a cooldown**
    - **Validates: Requirements 4.1, 4.2**

  - [x] 2.7 Implement cooldown lookup and ability-gating functions
    - `getRemainingCooldown(cooldowns, abilityId)` — missing key treated as 0
    - `canUseAbility(remainingCooldown, mana, manaCost, canAct)`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 2.8 Write property test for cooldown indicator visibility
    - **Property 1: Cooldown indicator visibility matches remaining cooldown**
    - **Validates: Requirements 1.1, 1.2, 1.5**

  - [x] 2.9 Write property test for ability usability gating
    - **Property 2: Ability usability is exactly the conjunction of its gating conditions**
    - **Validates: Requirements 1.3, 1.4**

- [x] 3. Implement `frontend/src/hooks/useIsTouchDevice.ts`
  - [x] 3.1 Implement `useIsTouchDevice()` using `@base-ui/react`'s `useMediaQuery("(hover: none)", { defaultMatches: false, noSsr: true })`
    - _Requirements: 2.3, 4.7_

  - [x] 3.2 Write unit test for `useIsTouchDevice`
    - Returns `true`/`false` based on a mocked `(hover: none)` media query match, and re-evaluates on a simulated change event
    - _Requirements: 2.3, 4.7_

- [x] 4. Implement `frontend/src/hooks/useInfoDisclosure.ts` — shared disclosure state machine
  - [x] 4.1 Implement the standalone `reduce`/`isOpen` pair and the `DisclosureState`/`Action` types
    - `isOpen(s) = s.pinned || s.hovering || s.focused || s.touchOpen`
    - Actions: `HOVER_ENTER`, `HOVER_LEAVE_CONFIRMED`, `FOCUS_IN`, `FOCUS_OUT`, `TOUCH_TOGGLE`, `PIN`, `UNPIN_AND_CLOSE`
    - Export `reduce`/`isOpen` standalone (decoupled from React) so they can be exercised directly by property tests
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 4.3, 5.1, 5.2, 5.5, 5.6, 5.7, 6.1, 6.2_

  - [x] 4.2 Write property test for disclosure visibility invariant
    - **Property 3: Disclosure visibility is exactly hovering-or-focused-or-touchOpen-or-pinned**
    - **Validates: Requirements 2.1, 2.2, 3.1, 3.2, 3.3, 4.3, 5.1, 5.2, 5.5, 5.7, 6.1, 6.2**

  - [x] 4.3 Write property test for touch toggle self-inverse
    - **Property 4: Touch toggle is self-inverse**
    - **Validates: Requirements 2.4, 3.3, 4.8, 5.7**

  - [x] 4.4 Implement the `useInfoDisclosure(options)` hook wrapping the reducer with React state
    - Wire `disabled` to short-circuit `triggerProps`/`toggleTouch`/pin dispatch to no-ops (Requirement 2.9)
    - Wire `hoverOutGraceMs`: `setTimeout` before dispatching `HOVER_LEAVE_CONFIRMED`; `HOVER_ENTER` clears any pending timeout first
    - Build `triggerProps` (`onMouseEnter`, `onMouseLeave`, `onFocus`, `onBlur`, `onKeyDown` for Enter/Space-to-pin when `pinnable`, `aria-describedby`), a stable `panelId` (Requirement 6.3), `toggleTouch`, and `unpinAndClose`
    - _Requirements: 2.9, 4.4, 4.5, 4.6, 5.3, 5.4, 5.6, 6.3, 6.4_

  - [x] 4.5 Write property test for hover-out grace window
    - **Property 5: Hover-out grace window**
    - **Validates: Requirements 4.4, 4.5, 4.6**
    - Use fake timers (`vi.useFakeTimers()`) with a generated leave/re-entry gap

  - [x] 4.6 Write property test for disabled disclosure no-op
    - **Property 11: A disabled disclosure is a total no-op**
    - **Validates: Requirements 2.9**

  - [x] 4.7 Write property test for pin behavior
    - **Property 12: Pinning always opens and marks pinned, from any reachable state**
    - **Validates: Requirements 5.3, 5.4, 6.4**

  - [x] 4.8 Write property test for unpin-and-close reset
    - **Property 13: Unpin-and-close always fully resets, from any reachable state**
    - **Validates: Requirements 5.6**

- [x] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement `frontend/src/components/AbilityInfoPanel.tsx`
  - [x] 6.1 Implement the presentational panel
    - `role="tooltip"`, `id={id}` (matches a `useInfoDisclosure().panelId`), renders `fields.description`, `fields.dmg`, `fields.effect`, and `fields.lore` when present, plus optional `name` (for enemy abilities)
    - Takes only already-derived `AbilityInfoFields` — never touches raw `Ability`/`EnemyAbility` objects
    - _Requirements: 2.1, 2.6, 4.3_

  - [x] 6.2 Write unit tests for `AbilityInfoPanel`
    - Renders description, damage, effect, and lore when provided; omits lore section when absent (enemy usage); `id` prop is applied to the root element
    - _Requirements: 2.1, 2.6, 4.3_

- [x] 7. Implement `frontend/src/components/StatInfoPanel.tsx`
  - [x] 7.1 Implement the presentational panel
    - Renders `title` and `rows` (`{label, value}[]`) in the order passed in; renders a close control calling `onClose` iff `isPinned` is true (Requirement 5.10); no close control when `isPinned` is falsy/absent
    - _Requirements: 3.1, 5.1, 5.10_

  - [x] 7.2 Write unit tests for `StatInfoPanel`
    - Renders all provided rows in order; close control present only when `isPinned` is true and calls `onClose` when activated; close control absent when `isPinned` is false/undefined
    - _Requirements: 5.10_

- [x] 8. Implement `frontend/src/components/InfoIcon.tsx`
  - [x] 8.1 Implement the touch-only tap target
    - Renders a small "ⓘ" control with an accessible `label`, `aria-controls`, and calls `onToggle` on activation; structurally a sibling of its trigger (parent decides when to render it based on `useIsTouchDevice()`), never nested inside the trigger's own interactive element
    - _Requirements: 2.3, 2.4, 4.7, 4.8_

  - [x] 8.2 Write unit tests for `InfoIcon`
    - Calls `onToggle` on click/tap; exposes the accessible `label` and `aria-controls`
    - _Requirements: 2.3, 2.4, 4.7, 4.8_

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Wire cooldown indicator, ability info panel, and touch InfoIcon into `ActionButtons.tsx` (Requirements 1, 2)
  - [x] 10.1 Modify `frontend/src/components/ActionButtons.tsx`
    - Add a `CooldownIndicator` badge per ability, sourced from `getRemainingCooldown(cooldowns, ability.id)`, rendered as a visual element separate from the existing "MP" label (distinct icon/label/position, not color alone)
    - Compute `canUse` via `canUseAbility(remaining, mana, ability.mana_cost, !disabled)`; disable the button accordingly
    - Create a `useInfoDisclosure({ disabled: !canUse })` per ability; spread `triggerProps` onto the button (hover/focus open the panel); render `AbilityInfoPanel` when `isOpen`, using `getAbilityInfoFields(ability)`
    - When `useIsTouchDevice()` is true, render an `InfoIcon` sibling per ability calling `disclosure.toggleTouch`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 6.1, 6.2, 6.3_

  - [x] 10.2 Write unit/RTL tests for `ActionButtons` wiring
    - Cooldown badge renders with the exact remaining value when > 0 and is absent when 0/missing; disabled state while on cooldown regardless of mana/turn phase
    - Hover/focus opens the ability's `AbilityInfoPanel`; leave/blur closes it
    - `InfoIcon` renders only under a mocked touch-device state and tapping it toggles the panel without submitting the ability
    - Tapping the enabled button outside the icon submits the ability without opening the panel
    - Tapping a disabled button (icon or elsewhere) does not submit the action and does not change panel visibility
    - `aria-describedby` on the button matches the panel's `id` when the panel is open
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.9, 6.1, 6.2, 6.3_

- [x] 11. Wire avatar stat panel, enemy ability list, and pinning into `CatCard.tsx` (Requirements 3, 4, 5, 6)
  - [x] 11.1 Modify `frontend/src/components/CatCard.tsx` — avatar stat-panel trigger
    - Add new optional props: `statPanel?: PlayerStatFields | EnemyStatFields`, `statPanelTitle?: string`, `pinnable?: boolean` (default `false`)
    - When `statPanel` is provided, make the avatar element `tabIndex={0}`, `role="button"`, give it an accessible name, and spread `useInfoDisclosure({ pinnable }).triggerProps` onto it; render `StatInfoPanel` beside it when open, with `rows` built from the field object in the requirement-specified order
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 5.1, 5.2, 5.8, 5.9, 6.1, 6.2, 6.3_

  - [x] 11.2 Modify `frontend/src/components/CatCard.tsx` — enemy ability list
    - Add new optional props: `abilityList?: EnemyAbilityListEntry[]`, `abilityFieldsById?: Record<string, AbilityInfoFields>`
    - When `abilityList` is provided, render an inline list of ability names below the stat row; each entry gets its own `useInfoDisclosure({ hoverOutGraceMs: 150 })`, its own `AbilityInfoPanel` sourced from `abilityFieldsById[entry.id]`, and (touch only) its own `InfoIcon`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 6.1, 6.2, 6.3_

  - [x] 11.3 Modify `frontend/src/components/CatCard.tsx` — pinning
    - When `pinnable` and the avatar's panel is open: click (non-touch) or Enter/Space while focused (non-touch) dispatches `PIN`
    - Render `StatInfoPanel`'s close control (`onClose`) wired to `unpinAndClose`; touch device taps the avatar to toggle instead of pinning
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 6.4_

  - [x] 11.4 Write unit/RTL tests for `CatCard` wiring
    - Existing `CatCard.test.tsx` assertions (emoji fallback, `<img>` rendering) remain valid and green with no props passed
    - Hover/focus on the avatar opens its `StatInfoPanel`; leave/blur closes it unless pinned; touch tap toggles it
    - Enemy ability list renders ability names with no cooldown value ever rendered; hovering an entry, leaving, and re-entering within 150ms keeps its panel open without an observable close; re-entering after 150ms shows it as a fresh hover
    - Click (non-touch) pins the enemy avatar's open `StatInfoPanel`; Enter/Space while focused and open also pins it; the panel stays visible after the pointer/focus moves away once pinned
    - Clicking/tapping the pinned panel's close control hides it and clears pinned state
    - `aria-describedby` on the avatar and each ability-list entry matches their respective panel `id` when open
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.4, 4.5, 4.6, 4.7, 4.8, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.10, 6.1, 6.2, 6.3, 6.4_

- [x] 12. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Wire field-object construction into `BattleArena.tsx` and `BattlePage.tsx` (Requirements 3, 4, 5, 7)
  - [x] 13.1 Modify `frontend/src/components/BattleArena.tsx`
    - Additively widen the `player`/`enemy` prop shapes to accept `statPanel`, `statPanelTitle`, `abilityList`, `abilityFieldsById`, `pinnable` and pass them through to the corresponding `CatCard` instance (enemy `CatCard` gets `abilityList`/`abilityFieldsById`/`pinnable`; both get `statPanel`/`statPanelTitle`)
    - _Requirements: 3.1, 4.1, 5.1, 7.3_

  - [x] 13.2 Modify `frontend/src/pages/BattlePage.tsx`
    - Build the player's `statPanel` via `getPlayerStatFields(cat)`, the enemy's `statPanel` via `getEnemyStatFields(gameState.enemy)`, the enemy's `abilityList` via `toEnemyAbilityList(gameState.enemy)`, and `abilityFieldsById` via `getEnemyAbilityInfoFields` mapped over `gameState.enemy.abilities`
    - Pass all of the above into `BattleArena`; set `pinnable` on the enemy card
    - Do not add, remove, rename, or retype any field on `BattleStateResponse`/`BattleActionResponse`/`GameState`/`Enemy`/`EnemyAbility`/`Ability`/`CatResponse`, and do not call any Battle API endpoint beyond the existing start/action endpoints
    - _Requirements: 3.4, 3.5, 4.1, 4.2, 5.1, 5.8, 5.9, 7.1, 7.2, 7.3_

  - [x] 13.3 Write integration tests for `BattleArena`/`BattlePage` wiring
    - Existing `BattlePage.test.tsx` assertions remain green
    - The player and enemy `CatCard` instances receive `statPanel` data matching `getPlayerStatFields(cat)`/`getEnemyStatFields(gameState.enemy)`
    - The enemy `CatCard` receives `abilityList`/`abilityFieldsById` matching `toEnemyAbilityList`/`getEnemyAbilityInfoFields` output, and `pinnable=true`
    - _Requirements: 3.4, 3.5, 4.1, 4.2, 5.1, 5.8, 5.9_

- [x] 14. Final checkpoint — Ensure all tests pass
  - Run the full frontend suite (`vitest --run`) and `npm run build`; confirm every property test, unit test, and integration test is green with no regressions to existing Battle screen tests
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP; core implementation tasks are never optional.
- Property tests (tasks 2.2–2.6, 2.8–2.9, 4.2–4.3, 4.5–4.8) validate the thirteen correctness properties from the design document against the pure functions in `lib/battleInfo.ts` and the `useInfoDisclosure` reducer, decoupled from React rendering.
- Accessibility (Requirement 6) is implemented inside `useInfoDisclosure` (task 4) and verified inline within the `ActionButtons`/`CatCard` wiring tests (tasks 10.2, 11.4) rather than as a separate task.
- No backend changes are made at any point in this plan; all panel/badge content is derived exclusively from fields already present on `BattleStateResponse`/`BattleActionResponse` via `lib/battleInfo.ts`.
- `CatCardProps`/`BattleArenaProps` are only ever extended with new optional props — no existing prop is removed, renamed, or retyped, so existing callers and tests are unaffected.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "4.1"] },
    { "id": 1, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "3.2", "4.4"] },
    { "id": 2, "tasks": ["2.8", "2.9", "4.2", "4.3", "4.5", "4.6", "4.7", "4.8"] },
    { "id": 3, "tasks": ["6.1", "7.1", "8.1"] },
    { "id": 4, "tasks": ["6.2", "7.2", "8.2"] },
    { "id": 5, "tasks": ["10.1"] },
    { "id": 6, "tasks": ["10.2", "11.1"] },
    { "id": 7, "tasks": ["11.2"] },
    { "id": 8, "tasks": ["11.3"] },
    { "id": 9, "tasks": ["11.4", "13.1"] },
    { "id": 10, "tasks": ["13.2"] },
    { "id": 11, "tasks": ["13.3"] }
  ]
}
```
