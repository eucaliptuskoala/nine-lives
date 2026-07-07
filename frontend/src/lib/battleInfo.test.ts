import { describe, it, expect } from "vitest";
import fc from "fast-check";

import {
  canUseAbility,
  getAbilityInfoFields,
  getEnemyAbilityInfoFields,
  getEnemyStatFields,
  getPlayerStatFields,
  getRemainingCooldown,
  toEnemyAbilityList,
  PLACEHOLDER_TEXT,
  NO_EFFECT_TEXT,
} from "@/lib/battleInfo";
import type { Ability, Cat, Enemy, EnemyAbility, Effect } from "@/types/game";

const effectArb: fc.Arbitrary<Effect | null> = fc.constantFrom(
  "STUN",
  "SILENCE",
  "BLEED",
  "BURN",
  "BLIND",
  "SLOW",
  "TAUNT",
  "REGEN",
  null,
);

const enemyAbilityArb: fc.Arbitrary<EnemyAbility> = fc.record({
  id: fc.string(),
  name: fc.string(),
  dmg: fc.integer({ min: -1000, max: 1000 }),
  type: fc.constantFrom("DMG", "HEAL", "STEAL", "SHIELD", "AOE", "COUNTER", "TRUE_DMG"),
  effect: effectArb,
  mana_cost: fc.integer({ min: 0, max: 100 }),
  cooldown: fc.integer({ min: 0, max: 20 }),
  is_special: fc.boolean(),
  description: fc.string(),
});

/**
 * Builds an Enemy generator whose numeric fields (atk, defence, spd, max_hp,
 * max_mana) are drawn from a shared small integer pool, and whose
 * `ability_cooldowns` values are drawn adversarially from that SAME pool —
 * so cooldown values frequently coincide numerically with the other fields.
 * This is the adversarial case the property requires: even when a cooldown
 * value equals e.g. `atk` by coincidence, the result must never be sourced
 * from `ability_cooldowns`.
 */
const enemyArb: fc.Arbitrary<Enemy> = fc
  .tuple(
    fc.string(),
    fc.string(),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.integer({ min: 0, max: 999 }),
    fc.array(enemyAbilityArb, { minLength: 0, maxLength: 5 }),
    fc.string(),
  )
  .chain(
    ([
      name,
      breed,
      hp,
      max_hp,
      atk,
      defence,
      shield,
      spd,
      mana,
      max_mana,
      abilities,
      avatar_url,
    ]) => {
      // Adversarial cooldown pool: values are drawn from the SAME numeric
      // pool used for atk/defence/spd/max_hp/max_mana, so they frequently
      // coincide with one of those fields by construction.
      const numericPool = [atk, defence, spd, max_hp, max_mana, hp, shield, mana];
      const cooldownValueArb = fc.oneof(
        fc.constantFrom(...numericPool),
        fc.integer({ min: 0, max: 999 }),
      );
      const abilityIds = abilities.map((a) => a.id);
      const cooldownKeyArb =
        abilityIds.length > 0
          ? fc.oneof(fc.constantFrom(...abilityIds), fc.string())
          : fc.string();

      return fc
        .dictionary(cooldownKeyArb, cooldownValueArb, { maxKeys: 8 })
        .map(
          (ability_cooldowns): Enemy => ({
            name,
            breed,
            hp,
            max_hp,
            atk,
            defence,
            shield,
            spd,
            mana,
            max_mana,
            ability_cooldowns,
            abilities,
            avatar_url,
          }),
        );
    },
  );

describe("getEnemyStatFields", () => {
  // Feature: battle-info-tooltips, Property 9: Enemy stat panel content excludes cooldowns and contains exactly six fields
  it("contains exactly six fields matching Enemy, and never sources a value from ability_cooldowns, even adversarially", () => {
    fc.assert(
      fc.property(enemyArb, (enemy) => {
        const result = getEnemyStatFields(enemy);

        // Exactly the six keys: breed, atk, defence, spd, maxHp, maxMana.
        const keys = Object.keys(result).sort();
        expect(keys).toEqual(["atk", "breed", "defence", "maxHp", "maxMana", "spd"].sort());

        // Each value equals the corresponding Enemy field exactly.
        expect(result.breed).toBe(enemy.breed);
        expect(result.atk).toBe(enemy.atk);
        expect(result.defence).toBe(enemy.defence);
        expect(result.spd).toBe(enemy.spd);
        expect(result.maxHp).toBe(enemy.max_hp);
        expect(result.maxMana).toBe(enemy.max_mana);

        // Direct proof the function never reads ability_cooldowns, even in
        // the adversarial case where a cooldown value numerically coincides
        // with atk/defence/spd/maxHp/maxMana: recompute with a completely
        // different ability_cooldowns object and confirm the result is
        // identical.
        // recompute with a completely different ability_cooldowns object
        // and confirm the result is identical.
        const mutatedEnemy: Enemy = {
          ...enemy,
          ability_cooldowns: { mutated: 123456789 },
        };
        expect(getEnemyStatFields(mutatedEnemy)).toEqual(result);
      }),
      { numRuns: 100 },
    );
  });
});

describe("toEnemyAbilityList", () => {
  // Feature: battle-info-tooltips, Property 10: Enemy ability list entries preserve order and identity, and never leak a cooldown
  // Validates: Requirements 4.1, 4.2
  it("preserves order/identity of enemy.abilities, has exactly id+name keys, and never sources a value from ability_cooldowns, even adversarially", () => {
    fc.assert(
      fc.property(enemyArb, (enemy) => {
        const list = toEnemyAbilityList(enemy);

        // Same length and order as enemy.abilities.
        expect(list.length).toBe(enemy.abilities.length);
        list.forEach((entry, i) => {
          expect(entry.id).toBe(enemy.abilities[i].id);
          expect(entry.name).toBe(enemy.abilities[i].name);
          // Exactly the keys `id` and `name`.
          expect(Object.keys(entry).sort()).toEqual(["id", "name"]);
        });

        // Direct proof the function does not read ability_cooldowns at all:
        // recompute with a completely different ability_cooldowns object
        // (even one adversarially keyed/valued by ability ids/names) and
        // confirm the result is unaffected.
        const mutatedEnemy: Enemy = {
          ...enemy,
          ability_cooldowns: Object.fromEntries(
            enemy.abilities.map((a, i) => [a.id, i + 999999]),
          ),
        };
        expect(toEnemyAbilityList(mutatedEnemy)).toEqual(list);
      }),
      { numRuns: 100 },
    );
  });
});

describe("getAbilityInfoFields", () => {
  // Feature: battle-info-tooltips, Property 6: Player ability info content is a faithful, placeholder-safe projection
  // Validates: Requirements 2.6, 2.7, 2.8
  it("is a faithful, placeholder-safe projection of an Ability", () => {
    const nullishStringArb = fc.oneof(
      fc.string(),
      fc.constant(""),
      fc.constant(null),
      fc.constant(undefined),
    );

    const abilityArb = fc.record({
      id: fc.string(),
      creature_id: fc.string(),
      name: fc.string(),
      dmg: fc.integer({ min: -1000, max: 1000 }),
      type: fc.constantFrom("DMG", "HEAL", "STEAL", "SHIELD", "AOE", "COUNTER", "TRUE_DMG"),
      effect: effectArb,
      cooldown: fc.integer({ min: 0, max: 20 }),
      mana_cost: fc.integer({ min: 0, max: 100 }),
      lore: nullishStringArb,
      is_special: fc.boolean(),
      description: nullishStringArb,
    }) as fc.Arbitrary<Ability>;

    fc.assert(
      fc.property(abilityArb, (ability) => {
        const result = getAbilityInfoFields(ability);

        // dmg is a direct passthrough.
        expect(result.dmg).toBe(ability.dmg);

        // description follows the placeholder rule.
        if (
          ability.description == null ||
          (ability.description as unknown as string) === ""
        ) {
          expect(result.description).toBe(PLACEHOLDER_TEXT);
        } else {
          expect(result.description).toBe(ability.description);
        }

        // lore follows the same placeholder rule.
        if (ability.lore == null || (ability.lore as unknown as string) === "") {
          expect(result.lore).toBe(PLACEHOLDER_TEXT);
        } else {
          expect(result.lore).toBe(ability.lore);
        }

        // effect: null maps to NO_EFFECT_TEXT, otherwise passthrough.
        if (ability.effect === null) {
          expect(result.effect).toBe(NO_EFFECT_TEXT);
        } else {
          expect(result.effect).toBe(ability.effect);
        }

        // The placeholder and no-effect sentinels are always distinct.
        expect(NO_EFFECT_TEXT).not.toBe(PLACEHOLDER_TEXT);
      }),
      { numRuns: 100 },
    );
  });
});

describe("getEnemyAbilityInfoFields", () => {
  // Feature: battle-info-tooltips, Property 7: Enemy ability info content is a faithful, placeholder-safe projection
  // Validates: Requirements 4.3
  it("is a faithful, placeholder-safe projection of an EnemyAbility, and never contains a lore field", () => {
    fc.assert(
      fc.property(enemyAbilityArb, (ability) => {
        const result = getEnemyAbilityInfoFields(ability);

        // dmg is a direct passthrough.
        expect(result.dmg).toBe(ability.dmg);

        // description follows the same placeholder rule as Property 6.
        if (ability.description == null || ability.description === "") {
          expect(result.description).toBe(PLACEHOLDER_TEXT);
        } else {
          expect(result.description).toBe(ability.description);
        }

        // effect follows the same no-effect rule as Property 6.
        if (ability.effect === null) {
          expect(result.effect).toBe(NO_EFFECT_TEXT);
        } else {
          expect(result.effect).toBe(ability.effect);
        }

        // The result never contains a lore field (EnemyAbility has none).
        expect("lore" in result).toBe(false);
        expect(result.lore).toBeUndefined();
      }),
      { numRuns: 100 },
    );
  });
});

describe("getPlayerStatFields", () => {
  // Feature: battle-info-tooltips, Property 8: Player stat panel content is a faithful, placeholder-safe projection
  // Validates: Requirements 3.4, 3.5
  it("is a faithful, placeholder-safe projection of a Cat", () => {
    const nullishStringArb = fc.oneof(
      fc.string(),
      fc.constant(""),
      fc.constant(null),
      fc.constant(undefined),
    );

    const abilityArbForCat: fc.Arbitrary<Ability> = fc.record({
      id: fc.string(),
      creature_id: fc.string(),
      name: fc.string(),
      dmg: fc.integer({ min: -1000, max: 1000 }),
      type: fc.constantFrom("DMG", "HEAL", "STEAL", "SHIELD", "AOE", "COUNTER", "TRUE_DMG"),
      effect: effectArb,
      cooldown: fc.integer({ min: 0, max: 20 }),
      mana_cost: fc.integer({ min: 0, max: 100 }),
      lore: fc.string(),
      is_special: fc.boolean(),
      description: fc.string(),
    });

    const catArb: fc.Arbitrary<Cat> = fc.record({
      id: fc.string(),
      name: fc.string(),
      breed: nullishStringArb,
      class: fc.constantFrom("STRENGTH", "AGILITY", "INTELLIGENCE"),
      current_hp: fc.integer({ min: 0, max: 1000 }),
      max_hp: fc.integer({ min: 0, max: 1000 }),
      dmg: fc.integer({ min: -1000, max: 1000 }),
      defence: fc.integer({ min: -1000, max: 1000 }),
      spd: fc.integer({ min: -1000, max: 1000 }),
      mana: fc.integer({ min: 0, max: 1000 }),
      max_mana: fc.integer({ min: 0, max: 1000 }),
      lore: nullishStringArb,
      avatar_url: fc.string(),
      lives_remaining: fc.integer({ min: 0, max: 9 }),
      abilities: fc.array(abilityArbForCat, { minLength: 0, maxLength: 5 }),
      user_id: fc.string(),
      source_image_url: fc.string(),
      status: fc.constantFrom("ALIVE", "MEMORIAL"),
      wins: fc.integer({ min: 0, max: 1000 }),
      death_date: fc.oneof(fc.string(), fc.constant(null)),
      personal_note: fc.oneof(fc.string(), fc.constant(null)),
      personality: fc.oneof(fc.string(), fc.constant(null)),
      created_at: fc.string(),
    }) as fc.Arbitrary<Cat>;

    fc.assert(
      fc.property(catArb, (cat) => {
        const result = getPlayerStatFields(cat);

        // dmg, defence, spd, maxHp, maxMana are direct passthroughs.
        expect(result.dmg).toBe(cat.dmg);
        expect(result.defence).toBe(cat.defence);
        expect(result.spd).toBe(cat.spd);
        expect(result.maxHp).toBe(cat.max_hp);
        expect(result.maxMana).toBe(cat.max_mana);

        // breed follows the placeholder rule.
        if (cat.breed == null || (cat.breed as unknown as string) === "") {
          expect(result.breed).toBe(PLACEHOLDER_TEXT);
        } else {
          expect(result.breed).toBe(cat.breed);
        }

        // lore follows the same placeholder rule.
        if (cat.lore == null || (cat.lore as unknown as string) === "") {
          expect(result.lore).toBe(PLACEHOLDER_TEXT);
        } else {
          expect(result.lore).toBe(cat.lore);
        }
      }),
      { numRuns: 100 },
    );
  });
});

describe("getRemainingCooldown", () => {
  // Feature: battle-info-tooltips, Property 1: Cooldown indicator visibility matches remaining cooldown
  // Validates: Requirements 1.1, 1.2, 1.5
  it("shows a Cooldown_Indicator iff the remaining cooldown is > 0, and the displayed value matches exactly", () => {
    const abilityIdArb = fc.string({ minLength: 1 });

    // A cooldown map generator that deliberately covers all three required
    // cases for a given abilityId: absent entirely, present with 0, and
    // present with a positive value.
    const cooldownsAndIdArb = fc
      .tuple(
        abilityIdArb,
        fc.dictionary(fc.string(), fc.integer({ min: 0, max: 20 }), { maxKeys: 8 }),
        fc.constantFrom<"absent" | "zero" | "positive" | "asGenerated">(
          "absent",
          "zero",
          "positive",
          "asGenerated",
        ),
        fc.integer({ min: 1, max: 20 }),
      )
      .map(([abilityId, baseCooldowns, mode, positiveValue]) => {
        const cooldowns: Record<string, number> = { ...baseCooldowns };
        // Make sure the chosen abilityId doesn't collide with the mode we want.
        delete cooldowns[abilityId];

        if (mode === "zero") {
          cooldowns[abilityId] = 0;
        } else if (mode === "positive") {
          cooldowns[abilityId] = positiveValue;
        } else if (mode === "asGenerated") {
          // Leave it as whatever the dictionary happened to generate (which,
          // after the delete above, means "absent" for this key too) — this
          // branch still exercises arbitrary maps not specifically tailored
          // to abilityId, in addition to the explicit absent/zero/positive
          // cases above.
        }
        // "absent" mode: leave abilityId deleted from cooldowns.

        return { abilityId, cooldowns };
      });

    fc.assert(
      fc.property(cooldownsAndIdArb, ({ abilityId, cooldowns }) => {
        const remaining = getRemainingCooldown(cooldowns, abilityId);

        // Mirror the UI rule under test: a Cooldown_Indicator is shown iff
        // remaining > 0, and when shown its displayed value is `remaining`
        // exactly.
        const isIndicatorShown = remaining > 0;
        const displayedValue = isIndicatorShown ? remaining : undefined;

        if (abilityId in cooldowns) {
          expect(remaining).toBe(cooldowns[abilityId]);
        } else {
          expect(remaining).toBe(0);
        }

        expect(isIndicatorShown).toBe(remaining > 0);
        if (isIndicatorShown) {
          expect(displayedValue).toBe(remaining);
        } else {
          expect(displayedValue).toBeUndefined();
        }
      }),
      { numRuns: 100 },
    );
  });

  it("treats a missing key as 0 (no indicator)", () => {
    expect(getRemainingCooldown({}, "fireball")).toBe(0);
  });

  it("returns 0 for a present key with value 0 (no indicator)", () => {
    expect(getRemainingCooldown({ fireball: 0 }, "fireball")).toBe(0);
  });

  it("returns the exact positive value for a present key (indicator shown with that value)", () => {
    expect(getRemainingCooldown({ fireball: 3 }, "fireball")).toBe(3);
  });
});

describe("canUseAbility", () => {
  // Feature: battle-info-tooltips, Property 2: Ability usability is exactly the conjunction of its gating conditions
  // Validates: Requirements 1.3, 1.4
  it("is true iff remainingCooldown === 0 AND mana >= manaCost AND canAct", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 20 }),
        fc.integer({ min: 0, max: 1000 }),
        fc.integer({ min: 0, max: 1000 }),
        fc.boolean(),
        (remainingCooldown, mana, manaCost, canAct) => {
          const result = canUseAbility(remainingCooldown, mana, manaCost, canAct);
          const expected = remainingCooldown === 0 && mana >= manaCost && canAct;
          expect(result).toBe(expected);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("is always false whenever remainingCooldown > 0, regardless of mana/manaCost/canAct", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 20 }),
        fc.integer({ min: 0, max: 1000 }),
        fc.integer({ min: 0, max: 1000 }),
        fc.boolean(),
        (remainingCooldown, mana, manaCost, canAct) => {
          expect(canUseAbility(remainingCooldown, mana, manaCost, canAct)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });
});
