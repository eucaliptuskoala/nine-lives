import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Mock } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import type { Ability, Cat, Enemy, GameState } from "../types/game";
import type { UseGameStateReturn } from "../hooks/useGameState";

// --- Router: keep MemoryRouter/Routes/Route/useParams real, spy on navigate ---
const navigateMock = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

// --- Drive the game-state hook directly (no network) ---
vi.mock("../hooks/useGameState");
import { useGameState } from "../hooks/useGameState";
import BattlePage from "./BattlePage";

const useGameStateMock = vi.mocked(useGameState);

// --- Realistic fixtures consistent with src/types/game.ts ---
const ability: Ability = {
  id: "ab-1",
  creature_id: "cat-1",
  name: "Pounce",
  dmg: 12,
  type: "DMG",
  effect: null,
  cooldown: 2,
  mana_cost: 10,
  lore: "",
  is_special: false,
  description: "A quick strike.",
};

const enemy: Enemy = {
  name: "Rival",
  breed: "Alley",
  hp: 80,
  max_hp: 80,
  atk: 8,
  defence: 4,
  shield: 0,
  spd: 6,
  mana: 50,
  max_mana: 50,
  ability_cooldowns: {},
  abilities: [],
  avatar_url: "",
};

const baseGameState: GameState = {
  player_hp: 100,
  player_max_hp: 100,
  player_mana: 100,
  player_max_mana: 100,
  player_is_defending: false,
  player_shield: 0,
  lives_remaining: 9,
  player_ability_cooldowns: {},
  phase: "PLAYER_TURN",
  current_round: 1,
  enemy,
};

const baseCat: Cat = {
  id: "cat-1",
  name: "Whiskers",
  breed: "Tabby",
  class: "STRENGTH",
  current_hp: 100,
  max_hp: 100,
  dmg: 10,
  defence: 5,
  spd: 5,
  mana: 100,
  max_mana: 100,
  lore: "",
  avatar_url: "",
  lives_remaining: 9,
  abilities: [ability],
  user_id: "user-1",
  source_image_url: "",
  status: "ALIVE",
  wins: 0,
  death_date: null,
  personal_note: null,
  personality: null,
  created_at: "2024-01-01T00:00:00Z",
};

let startBattle: Mock<UseGameStateReturn["startBattle"]>;
let submitAction: Mock<UseGameStateReturn["submitAction"]>;

function hookReturn(overrides: Partial<UseGameStateReturn> = {}): UseGameStateReturn {
  return {
    gameState: baseGameState,
    cat: baseCat,
    isLoading: false,
    error: null,
    revival: false,
    gameOver: false,
    sessionExpired: false,
    runEnded: false,
    events: [],
    startBattle,
    submitAction,
    ...overrides,
  };
}

function renderPage(overrides: Partial<UseGameStateReturn> = {}) {
  useGameStateMock.mockReturnValue(hookReturn(overrides));
  return render(
    <MemoryRouter initialEntries={["/battle/run-123"]}>
      <Routes>
        <Route path="/battle/:runId" element={<BattlePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("BattlePage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    startBattle = vi.fn<UseGameStateReturn["startBattle"]>();
    submitAction = vi.fn<UseGameStateReturn["submitAction"]>();
  });

  afterEach(() => {
    cleanup();
  });

  it("starts the battle on mount using the runId from the route", () => {
    renderPage();
    expect(startBattle).toHaveBeenCalledTimes(1);
    expect(startBattle).toHaveBeenCalledWith("run-123");
  });

  it("submits 'attack' when the Attack button is clicked", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /attack/i }));
    expect(submitAction).toHaveBeenCalledWith("attack");
  });

  it("submits 'defend' when the Defend button is clicked", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /defend/i }));
    expect(submitAction).toHaveBeenCalledWith("defend");
  });

  it("submits 'ability' with the ability id when an ability button is clicked", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /pounce/i }));
    expect(submitAction).toHaveBeenCalledWith("ability", "ab-1");
  });

  it("disables the action buttons while a turn is resolving (isLoading)", () => {
    renderPage({ isLoading: true });
    expect(screen.getByRole("button", { name: /attack/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /defend/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /pounce/i })).toBeDisabled();
  });

  it("renders the revival notification when a life was restored", () => {
    const { container } = renderPage({ revival: true });
    expect(container.textContent).toContain("has been revived");
    expect(container.textContent).toContain(baseCat.name);
  });

  it("navigates to the memorial when the run is over", () => {
    renderPage({ gameOver: true });
    expect(navigateMock).toHaveBeenCalledWith("/memorial");
  });

  it("shows the error message but keeps actions usable when an action fails", () => {
    const { container } = renderPage({ error: "Network error, try again." });
    expect(container.textContent).toContain("Network error, try again.");
    // gameState/cat are still present, so the player can retry the action.
    expect(screen.getByRole("button", { name: /attack/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /defend/i })).toBeEnabled();
  });
});
