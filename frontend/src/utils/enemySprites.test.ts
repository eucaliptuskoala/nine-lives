import { describe, it, expect } from "vitest";
import { ENEMY_SPRITES, getEnemySpriteUrl } from "./enemySprites";

describe("enemySprites", () => {
  it("resolves a URL for a bundled enemy name, case-insensitively", () => {
    // At least one sprite must be bundled for this test to be meaningful.
    const bundledNames = Object.keys(ENEMY_SPRITES);
    expect(bundledNames.length).toBeGreaterThan(0);

    const [name] = bundledNames;
    expect(getEnemySpriteUrl(name)).toBe(ENEMY_SPRITES[name]);
    expect(getEnemySpriteUrl(name.toUpperCase())).toBe(ENEMY_SPRITES[name]);
  });

  it("returns undefined for a name with no bundled sprite", () => {
    expect(getEnemySpriteUrl("Some Totally Unknown Enemy Name")).toBeUndefined();
  });
});
