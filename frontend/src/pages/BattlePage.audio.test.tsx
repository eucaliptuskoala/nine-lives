import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Mock } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import type { Ability, Cat, Enemy, GameState } from "../types/game";
import type { UseGameStateReturn } from "../hooks/useGameState";

// --- Router: keep everything real, spy on navigate ---
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => vi.fn() };
});

// --- Isolate the audio layer: replace useAudio with a spy-backed stub ---
const playMoveSound = vi.fn();
vi.mock("../hooks/useAudio", () => ({
  useAudio: () => ({
    muted: false,
    toggleMute: () => {},
    volume: 0.4,
    setVolume: () => {},
    playMoveSound,
  }),
}));

// --- Drive the game-state hook directly (no network) ---
vi.mock("../hooks/useGameState");
import { useGameState } from "../hooks/useGameState";
import BattlePage from "./BattlePage";

const useGameStateMock = vi.mocked(useGameState);

const regularAbility: Ability = {
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

const specialAbility: Ability = {
  id: "ab-2",
  creature_id: "cat-1",
  name: "Nine Tails Fury",
  dmg: 40,
  type: "TRUE_DMG",
  effect: null,
  cooldown: 5,
  mana_cost: 30,
  lore: "",
  is_special: true,
  description: "An ultimate blast.",
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
  abilities: [regularAbility, specialAbility],
  user_id: "user-1",
  source_image_url: "",
  status: "ALIVE",
  wins: 0,
  death_date: null,
  personal_note: null,
  personality: null,
  created_at: "2024-01-01T00:00:00Z",
};

let submitAction: Mock<UseGameStateReturn["submitAction"]>;

function renderPage() {
  useGameStateMock.mockReturnValue({
    gameState: baseGameState,
    cat: baseCat,
    isLoading: false,
    error: null,
    revival: false,
    gameOver: false,
    sessionExpired: false,
    runEnded: false,
    events: [],
    startBattle: vi.fn(),
    submitAction,
  });
  return render(
    <MemoryRouter initialEntries={["/battle/run-123"]}>
      <Routes>
        <Route path="/battle/:runId" element={<BattlePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("BattlePage per-move sound effects", () => {
  beforeEach(() => {
    playMoveSound.mockReset();
    submitAction = vi.fn<UseGameStateReturn["submitAction"]>();
  });

  afterEach(() => {
    cleanup();
  });

  it("plays 'attack' and still submits attack", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /attack/i }));
    expect(playMoveSound).toHaveBeenCalledWith("attack");
    expect(submitAction).toHaveBeenCalledWith("attack");
  });

  it("plays 'defend' (block_sound) and still submits defend", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /defend/i }));
    expect(playMoveSound).toHaveBeenCalledWith("defend");
    expect(submitAction).toHaveBeenCalledWith("defend");
  });

  it("plays 'ability' for a regular ability and submits with its id", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /pounce/i }));
    expect(playMoveSound).toHaveBeenCalledWith("ability");
    expect(submitAction).toHaveBeenCalledWith("ability", "ab-1");
  });

  it("plays 'ultimate' for a special ability and submits with its id", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /nine tails fury/i }));
    expect(playMoveSound).toHaveBeenCalledWith("ultimate");
    expect(submitAction).toHaveBeenCalledWith("ability", "ab-2");
  });
});
