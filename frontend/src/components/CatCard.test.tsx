import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import CatCard from "./CatCard";
import { Class } from "../types/game";
import type {
  AbilityInfoFields,
  EnemyAbilityListEntry,
  EnemyStatFields,
} from "@/lib/battleInfo";
import { useIsTouchDevice } from "@/hooks/useIsTouchDevice";

vi.mock("@/hooks/useIsTouchDevice", () => ({
  useIsTouchDevice: vi.fn(),
}));

const mockedUseIsTouchDevice = useIsTouchDevice as unknown as ReturnType<typeof vi.fn>;

const baseProps = {
  name: "Sir Pounce",
  classType: Class.STRENGTH,
  hp: 80,
  maxHp: 100,
  mana: 40,
  maxMana: 60,
};

describe("CatCard avatar rendering", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the emoji fallback when no avatarUrl is provided", () => {
    const { container } = render(<CatCard {...baseProps} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("\uD83D\uDC31")).toBeInTheDocument();
  });

  it("renders an img with the given avatarUrl when provided", () => {
    render(<CatCard {...baseProps} avatarUrl="https://example.com/sprite.png" />);
    const img = screen.getByRole("img", { name: /sir pounce avatar/i });
    expect(img.tagName).toBe("IMG");
    expect(img).toHaveAttribute("src", "https://example.com/sprite.png");
  });
});

describe("CatCard wiring (statPanel, abilityList, pinnable)", () => {
  afterEach(() => {
    cleanup();
    mockedUseIsTouchDevice.mockReset();
    vi.useRealTimers();
  });

  const enemyStatPanel: EnemyStatFields = {
    breed: "Alley Cat",
    atk: 15,
    defence: 10,
    spd: 12,
    maxHp: 100,
    maxMana: 50,
  };

  const abilityList: EnemyAbilityListEntry[] = [
    { id: "claw", name: "Claw Swipe" },
    { id: "hiss", name: "Hiss" },
  ];

  const abilityFieldsById: Record<string, AbilityInfoFields> = {
    claw: { description: "Swipes with claws.", dmg: 8, effect: "No effect." },
    hiss: { description: "Intimidates the foe.", dmg: 0, effect: "Lowers attack." },
  };

  describe("avatar Stat_Info_Panel disclosure", () => {
    it("opens on hover and closes on mouse leave when not pinned", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.mouseEnter(avatar);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.mouseLeave(avatar);
      expect(screen.queryByRole("tooltip")).toBeNull();
    });

    it("opens on focus and closes on blur when not pinned", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.focus(avatar);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.blur(avatar);
      expect(screen.queryByRole("tooltip")).toBeNull();
    });

    it("touch tap toggles the panel open and closed", () => {
      mockedUseIsTouchDevice.mockReturnValue(true);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.click(avatar);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.click(avatar);
      expect(screen.queryByRole("tooltip")).toBeNull();
    });
  });

  describe("Enemy_Ability_List", () => {
    it("renders each ability's name and never renders a cooldown value", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(
        <CatCard
          {...baseProps}
          abilityList={abilityList}
          abilityFieldsById={abilityFieldsById}
        />,
      );

      expect(screen.getByText("Claw Swipe")).toBeInTheDocument();
      expect(screen.getByText("Hiss")).toBeInTheDocument();
      expect(screen.queryByText(/cooldown/i)).toBeNull();

      const clawEntry = screen.getByRole("button", { name: "Claw Swipe info" });
      fireEvent.mouseEnter(clawEntry);
      const panel = screen.getByRole("tooltip");
      expect(panel).toHaveTextContent("Swipes with claws.");
      expect(panel.textContent).not.toMatch(/cooldown/i);
    });

    it("keeps an entry's panel open without an observable close when re-entering within 150ms", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      vi.useFakeTimers();
      render(
        <CatCard
          {...baseProps}
          abilityList={abilityList}
          abilityFieldsById={abilityFieldsById}
        />,
      );

      const clawEntry = screen.getByRole("button", { name: "Claw Swipe info" });

      fireEvent.mouseEnter(clawEntry);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.mouseLeave(clawEntry);
      act(() => {
        vi.advanceTimersByTime(100);
      });
      // Still within the 150ms grace window — must never be observed closed.
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.mouseEnter(clawEntry);
      act(() => {
        vi.advanceTimersByTime(150);
      });
      // Re-entry cancelled the pending close entirely.
      expect(screen.getByRole("tooltip")).toBeInTheDocument();
    });

    it("treats a re-entry after the 150ms grace window as a fresh hover", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      vi.useFakeTimers();
      render(
        <CatCard
          {...baseProps}
          abilityList={abilityList}
          abilityFieldsById={abilityFieldsById}
        />,
      );

      const clawEntry = screen.getByRole("button", { name: "Claw Swipe info" });

      fireEvent.mouseEnter(clawEntry);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.mouseLeave(clawEntry);
      act(() => {
        vi.advanceTimersByTime(200);
      });
      expect(screen.queryByRole("tooltip")).toBeNull();

      fireEvent.mouseEnter(clawEntry);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();
    });
  });

  describe("pinning the enemy avatar's Stat_Info_Panel", () => {
    it("click (non-touch) pins the open panel, keeping it visible after the pointer moves away", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} pinnable />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });

      fireEvent.mouseEnter(avatar);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.click(avatar);
      fireEvent.mouseLeave(avatar);

      expect(screen.getByRole("tooltip")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    });

    it("Enter/Space while focused and open also pins it, keeping it visible after focus moves away", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} pinnable />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });

      fireEvent.focus(avatar);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      fireEvent.keyDown(avatar, { key: "Enter" });
      fireEvent.blur(avatar);

      expect(screen.getByRole("tooltip")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    });

    it("clicking the pinned panel's close control hides it and clears pinned state", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} pinnable />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });

      fireEvent.mouseEnter(avatar);
      fireEvent.click(avatar);
      fireEvent.mouseLeave(avatar);
      expect(screen.getByRole("tooltip")).toBeInTheDocument();

      const closeButton = screen.getByRole("button", { name: "Close" });
      fireEvent.click(closeButton);

      expect(screen.queryByRole("tooltip")).toBeNull();
    });
  });

  describe("aria-describedby wiring", () => {
    it("matches the avatar panel's id when open, and is absent when closed", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(<CatCard {...baseProps} statPanel={enemyStatPanel} />);

      const avatar = screen.getByRole("button", { name: `${baseProps.name} stats` });
      expect(avatar).not.toHaveAttribute("aria-describedby");

      fireEvent.focus(avatar);
      const panel = screen.getByRole("tooltip");
      expect(avatar).toHaveAttribute("aria-describedby", panel.id);
    });

    it("matches each ability-list entry's panel id when open, and is absent when closed", () => {
      mockedUseIsTouchDevice.mockReturnValue(false);
      render(
        <CatCard
          {...baseProps}
          abilityList={abilityList}
          abilityFieldsById={abilityFieldsById}
        />,
      );

      const clawEntry = screen.getByRole("button", { name: "Claw Swipe info" });
      expect(clawEntry).not.toHaveAttribute("aria-describedby");

      fireEvent.focus(clawEntry);
      const panel = screen.getByRole("tooltip");
      expect(clawEntry).toHaveAttribute("aria-describedby", panel.id);
    });
  });
});
