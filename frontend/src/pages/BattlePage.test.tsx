import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Mock } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import type { Ability, Cat, Enemy, EnemyAbility, GameState } from "../types/game";
import type { UseGameStateReturn } from "../hooks/useGameState";
import {
  getEnemyAbilityInfoFields,
  getEnemyStatFields,
  getPlayerStatFields,
} from "@/lib/battleInfo";

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
    renderPage({ revival: true });
    expect(screen.getByText(/has been revived/i)).toBeInTheDocument();
    expect(screen.getByText(baseCat.name)).toBeInTheDocument();
  });

  it("shows a farewell screen and navigates to memorial on button click", () => {
    renderPage({ gameOver: true });
    expect(screen.getByText(/crossed the rainbow bridge/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Visit Memorial"));
    expect(navigateMock).toHaveBeenCalledWith("/memorial");
  });

  it("shows the error message but keeps actions usable when an action fails", () => {
    renderPage({ error: "Network error, try again." });
    expect(screen.getByText("Network error, try again.")).toBeInTheDocument();
    // gameState/cat are still present, so the player can retry the action.
    expect(screen.getByRole("button", { name: /attack/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /defend/i })).toBeEnabled();
  });

  it("shows a dismissible victory popup on round win and routes to /overworld on dismiss", () => {
    // Start on round 1 — no popup on first render.
    useGameStateMock.mockReturnValue(
      hookReturn({ gameState: { ...baseGameState, current_round: 1 } }),
    );
    const { rerender } = render(
      <MemoryRouter initialEntries={["/battle/run-123"]}>
        <Routes>
          <Route path="/battle/:runId" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Backend advances the round (enemy defeated) → popup appears.
    useGameStateMock.mockReturnValue(
      hookReturn({ gameState: { ...baseGameState, current_round: 2 } }),
    );
    rerender(
      <MemoryRouter initialEntries={["/battle/run-123"]}>
        <Routes>
          <Route path="/battle/:runId" element={<BattlePage />} />
        </Routes>
      </MemoryRouter>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/enemy defeated/i);

    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(navigateMock).toHaveBeenCalledWith("/overworld");
  });

  it("resolves and renders the bundled enemy sprite when the enemy's name matches one", () => {
    // "Shadow" has a bundled sprite (frontend/src/assets/enemies/shadow.jpeg);
    // BattlePage resolves it via getEnemySpriteUrl(gameState.enemy.name).
    renderPage({
      gameState: { ...baseGameState, enemy: { ...enemy, name: "Shadow" } },
    });

    const img = screen.getByRole("img", { name: /shadow avatar/i });
    expect(img.tagName).toBe("IMG");
    expect(img).toHaveAttribute("src");
    expect(img.getAttribute("src")).not.toBe("");
  });

  it("falls back to the emoji avatar when the enemy's name has no bundled sprite", () => {
    // Use an explicit unmatched name so the fallback path stays unambiguous
    // even as more enemy sprites are generated over time. The wrapper still
    // carries role="img" (for a11y, standing in for the fallback), but it
    // must not be a real <img> element since there's no sprite to load.
    const { container } = renderPage({
      gameState: {
        ...baseGameState,
        enemy: { ...enemy, name: "Some Totally Unknown Enemy Name" },
      },
    });
    expect(container.querySelector("img")).toBeNull();
  });
});

// --- Integration tests: BattlePage -> BattleArena -> CatCard wiring ---
// (Task 13.3 — Requirements 3.4, 3.5, 4.1, 4.2, 5.1, 5.8, 5.9)
//
// There is no dedicated BattleArena.test.tsx, so these verify the wiring
// through the BattlePage's rendered output: props that only take effect when
// they flow correctly through BattleArena into the player/enemy CatCard
// instances (statPanel, abilityList/abilityFieldsById, pinnable).
describe("BattlePage wiring into BattleArena/CatCard (statPanel, abilityList, pinnable)", () => {
  const swipeAbility: EnemyAbility = {
    id: "ea-1",
    name: "Swipe",
    dmg: 6,
    type: "DMG",
    effect: null,
    mana_cost: 5,
    cooldown: 1,
    is_special: false,
    description: "A swift claw swipe.",
  };

  const enemyWithAbility: Enemy = { ...enemy, abilities: [swipeAbility] };

  it("renders the Enemy_Ability_List entry sourced from toEnemyAbilityList(gameState.enemy)", () => {
    renderPage({ gameState: { ...baseGameState, enemy: enemyWithAbility } });

    expect(screen.getByRole("button", { name: /swipe info/i })).toBeInTheDocument();
  });

  it("the enemy ability list entry's Ability_Info_Panel content matches getEnemyAbilityInfoFields(ability)", () => {
    renderPage({ gameState: { ...baseGameState, enemy: enemyWithAbility } });

    const entry = screen.getByRole("button", { name: /swipe info/i });
    fireEvent.mouseEnter(entry);

    const panel = screen.getByRole("tooltip");
    const expectedFields = getEnemyAbilityInfoFields(swipeAbility);
    expect(panel).toHaveTextContent(expectedFields.description);
    expect(panel).toHaveTextContent(String(expectedFields.dmg));
    expect(panel).toHaveTextContent(expectedFields.effect);
  });

  it("renders the enemy avatar as an interactive Stat_Info_Panel trigger with content matching getEnemyStatFields(gameState.enemy)", () => {
    renderPage();

    const enemyAvatar = screen.getByRole("button", { name: /rival stats/i });
    fireEvent.mouseEnter(enemyAvatar);

    const panel = screen.getByRole("tooltip");
    const expected = getEnemyStatFields(enemy);
    expect(panel).toHaveTextContent(expected.breed);
    expect(panel).toHaveTextContent(String(expected.atk));
    expect(panel).toHaveTextContent(String(expected.defence));
    expect(panel).toHaveTextContent(String(expected.spd));
    expect(panel).toHaveTextContent(String(expected.maxHp));
    expect(panel).toHaveTextContent(String(expected.maxMana));
  });

  it("renders the player avatar as an interactive Stat_Info_Panel trigger with content matching getPlayerStatFields(cat)", () => {
    renderPage();

    const playerAvatar = screen.getByRole("button", { name: /whiskers stats/i });
    fireEvent.mouseEnter(playerAvatar);

    const panel = screen.getByRole("tooltip");
    const expected = getPlayerStatFields(baseCat);
    expect(panel).toHaveTextContent(String(expected.dmg));
    expect(panel).toHaveTextContent(String(expected.defence));
    expect(panel).toHaveTextContent(String(expected.spd));
    expect(panel).toHaveTextContent(String(expected.maxHp));
    expect(panel).toHaveTextContent(String(expected.maxMana));
    expect(panel).toHaveTextContent(expected.breed);
    expect(panel).toHaveTextContent(expected.lore);
  });

  it("the enemy avatar's Stat_Info_Panel is pinnable (BattlePage sets pinnable=true on the enemy)", () => {
    renderPage();

    const enemyAvatar = screen.getByRole("button", { name: /rival stats/i });
    fireEvent.mouseEnter(enemyAvatar);
    fireEvent.click(enemyAvatar);
    fireEvent.mouseLeave(enemyAvatar);

    // A close control is only ever rendered on a Pinned panel (Requirement
    // 5.10), so its presence after the pointer moves away proves both that
    // the panel opened and that it pinned.
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });

  it("the player avatar's Stat_Info_Panel is not pinnable (BattlePage does not set pinnable on the player)", () => {
    renderPage();

    const playerAvatar = screen.getByRole("button", { name: /whiskers stats/i });
    fireEvent.mouseEnter(playerAvatar);
    fireEvent.click(playerAvatar);
    fireEvent.mouseLeave(playerAvatar);

    // Without pinnable, clicking while open does not pin, so the panel
    // closes on mouse leave and no close control is ever rendered.
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
