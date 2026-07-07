import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import AbilityInfoPanel from "./AbilityInfoPanel";
import type { AbilityInfoFields } from "@/lib/battleInfo";

const fieldsWithLore: AbilityInfoFields = {
  description: "A swift pounce attack.",
  dmg: 15,
  effect: "Stuns the target.",
  lore: "Passed down through generations of alley cats.",
};

const fieldsWithoutLore: AbilityInfoFields = {
  description: "A vicious claw swipe.",
  dmg: 10,
  effect: "No effect.",
};

describe("AbilityInfoPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders description, damage, and effect from the fields prop", () => {
    render(<AbilityInfoPanel id="panel-1" fields={fieldsWithLore} />);

    expect(screen.getByText(fieldsWithLore.description)).toBeInTheDocument();
    expect(screen.getByText(String(fieldsWithLore.dmg))).toBeInTheDocument();
    expect(screen.getByText(fieldsWithLore.effect)).toBeInTheDocument();
  });

  it("renders lore text when fields.lore is present", () => {
    render(<AbilityInfoPanel id="panel-1" fields={fieldsWithLore} />);

    expect(screen.getByText(fieldsWithLore.lore as string)).toBeInTheDocument();
  });

  it("omits any lore section when fields.lore is undefined (enemy usage)", () => {
    render(<AbilityInfoPanel id="panel-1" fields={fieldsWithoutLore} />);

    expect(fieldsWithoutLore.lore).toBeUndefined();
    // Still renders the other fields.
    expect(screen.getByText(fieldsWithoutLore.description)).toBeInTheDocument();
    // No stray italic lore paragraph should be present.
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.querySelector("p.italic")).toBeNull();
  });

  it("applies the id prop to the root element", () => {
    render(<AbilityInfoPanel id="ability-panel-42" fields={fieldsWithLore} />);

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveAttribute("id", "ability-panel-42");
  });

  it("renders the name when provided (enemy ability usage)", () => {
    render(
      <AbilityInfoPanel id="panel-1" name="Shadow Claw" fields={fieldsWithoutLore} />,
    );

    expect(screen.getByText("Shadow Claw")).toBeInTheDocument();
  });

  it("does not render a name heading when name is omitted", () => {
    render(<AbilityInfoPanel id="panel-1" fields={fieldsWithLore} />);

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.querySelector("p.font-semibold")).toBeNull();
  });
});
