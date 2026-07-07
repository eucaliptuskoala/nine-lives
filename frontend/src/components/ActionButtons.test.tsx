import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import ActionButtons from "./ActionButtons";
import { AbilityType, type Ability } from "../types/game";
import { useIsTouchDevice } from "@/hooks/useIsTouchDevice";

vi.mock("@/hooks/useIsTouchDevice", () => ({
  useIsTouchDevice: vi.fn(),
}));

const mockedUseIsTouchDevice = useIsTouchDevice as unknown as ReturnType<typeof vi.fn>;

function makeAbility(overrides: Partial<Ability> = {}): Ability {
  return {
    id: "pounce",
    creature_id: "cat-1",
    name: "Pounce",
    dmg: 10,
    type: AbilityType.DMG,
    effect: null,
    cooldown: 3,
    mana_cost: 5,
    lore: "A swift leap.",
    is_special: false,
    description: "Leap at the enemy for damage.",
    ...overrides,
  };
}

const noop = () => {};

describe("ActionButtons wiring", () => {
  afterEach(() => {
    cleanup();
    mockedUseIsTouchDevice.mockReset();
  });

  describe("Cooldown_Indicator", () => {
    it("renders the exact remaining value when the ability's cooldown is greater than zero", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{ pounce: 3 }}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(button).toHaveTextContent("3t");
    });

    it("is absent when the ability's cooldown is zero", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{ pounce: 0 }}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(button).not.toHaveTextContent(/\d+t/);
    });

    it("is absent when the ability has no entry in the cooldowns map", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(button).not.toHaveTextContent(/\d+t/);
    });

    it("keeps the button disabled while on cooldown regardless of sufficient mana and an active turn phase", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility({ mana_cost: 5 });
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{ pounce: 2 }}
          mana={999}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(button).toBeDisabled();
    });

    it("keeps the button disabled while on cooldown even when mana is insufficient and disabled is true", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility({ mana_cost: 5 });
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{ pounce: 2 }}
          mana={0}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={true}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(button).toBeDisabled();
    });
  });

  describe("hover/focus disclosure", () => {
    it("opens the ability's AbilityInfoPanel on hover and closes it on mouse leave", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.mouseEnter(button);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.mouseLeave(button);
      expect(screen.queryByRole("tooltip")).toBeNull();
    });

    it("opens the ability's AbilityInfoPanel on focus and closes it on blur", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.focus(button);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.blur(button);
      expect(screen.queryByRole("tooltip")).toBeNull();
    });
  });

  describe("InfoIcon (touch device)", () => {
    it("renders only when the mocked touch-device state is true", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      const { rerender } = render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      expect(screen.queryByRole("button", { name: /toggle info for pounce/i })).toBeNull();

      mockedUseIsTouchDevice.mockReturnValue(true);
      rerender(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      expect(screen.getByRole("button", { name: /toggle info for pounce/i })).toBeInTheDocument();
    });

    it("tapping it toggles the panel without submitting the ability", () => {
      mockedUseIsTouchDevice.mockReturnValue(true);
      const ability = makeAbility();
      const onUseAbility = vi.fn();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={onUseAbility}
          disabled={false}
        />,
      );

      const icon = screen.getByRole("button", { name: /toggle info for pounce/i });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.click(icon);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();
      expect(onUseAbility).not.toHaveBeenCalled();

      fireEvent.click(icon);
      expect(screen.queryByRole("tooltip")).toBeNull();
      expect(onUseAbility).not.toHaveBeenCalled();
    });
  });

  describe("tapping the ability button", () => {
    it("submits the ability without opening the panel when enabled and tapped outside the icon", () => {
      mockedUseIsTouchDevice.mockReturnValue(true);
      const ability = makeAbility();
      const onUseAbility = vi.fn();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={onUseAbility}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      fireEvent.click(button);

      expect(onUseAbility).toHaveBeenCalledWith("pounce");
      expect(screen.queryByRole("tooltip")).toBeNull();
    });

    it("does not submit the action or change panel visibility when tapping a disabled button elsewhere", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility({ mana_cost: 5 });
      const onUseAbility = vi.fn();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{ pounce: 1 }}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={onUseAbility}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.click(button);

      expect(onUseAbility).not.toHaveBeenCalled();
      expect(screen.queryByRole("tooltip")).toBeNull();
    });

    it("does not submit the action or change panel visibility when tapping a disabled button's InfoIcon", () => {
      mockedUseIsTouchDevice.mockReturnValue(true);
      const ability = makeAbility({ mana_cost: 5 });
      const onUseAbility = vi.fn();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{ pounce: 1 }}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={onUseAbility}
          disabled={false}
        />,
      );

      const icon = screen.getByRole("button", { name: /toggle info for pounce/i });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.click(icon);

      expect(onUseAbility).not.toHaveBeenCalled();
      expect(screen.queryByRole("tooltip")).toBeNull();
    });
  });

  describe("aria-describedby wiring", () => {
    it("matches the panel's id when the panel is open, and is absent when closed", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      const ability = makeAbility();
      render(
        <ActionButtons
          abilities={[ability]}
          cooldowns={{}}
          mana={20}
          onAttack={noop}
          onDefend={noop}
          onUseAbility={noop}
          disabled={false}
        />,
      );

      const button = screen.getByRole("button", { name: /^pounce/i });
      expect(button).not.toHaveAttribute("aria-describedby");

      fireEvent.focus(button);
      const panel = screen.getByRole("tooltip");
      expect(button).toHaveAttribute("aria-describedby", panel.id);
    });
  });
});
