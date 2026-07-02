import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import type { Ability, Cat } from "../types/game";

// --- Supabase: useMemorial -> api/data -> authFetch imports `supabase`.
// We mock `../api/data` below so authFetch never runs, but the module graph
// still resolves the import, so provide a minimal stub client. ---
vi.mock("../hooks/useSupabase", () => ({
  useAuth: () => ({ user: { id: "user-1" }, session: null, loading: false }),
  supabase: {},
}));

// --- Data API: mocked so no network happens. The REAL useMemorial hook logic
// runs against these mocked calls, giving a true hook + page integration test. ---
vi.mock("../api/data");

import { getMemorialCats, updateCatNote } from "../api/data";
import MemorialPage from "./MemorialPage";

const getMemorialCatsMock = vi.mocked(getMemorialCats);
const updateCatNoteMock = vi.mocked(updateCatNote);

// --- Realistic fixtures consistent with src/types/game.ts ---
const specialAbility: Ability = {
  id: "ab-special",
  creature_id: "cat-1",
  name: "Phantom Pounce",
  dmg: 30,
  type: "TRUE_DMG",
  effect: "STUN",
  cooldown: 4,
  mana_cost: 40,
  lore: "A strike from beyond.",
  is_special: true,
  description: "Ignores defence and stuns.",
};

const basicAbility: Ability = {
  id: "ab-basic",
  creature_id: "cat-1",
  name: "Swipe",
  dmg: 12,
  type: "DMG",
  effect: null,
  cooldown: 1,
  mana_cost: 10,
  lore: "",
  is_special: false,
  description: "A quick claw swipe.",
};

function makeCat(overrides: Partial<Cat> = {}): Cat {
  return {
    id: "cat-1",
    name: "Whiskers",
    breed: "Tabby",
    class: "STRENGTH",
    current_hp: 0,
    max_hp: 120,
    dmg: 18,
    defence: 9,
    spd: 7,
    mana: 60,
    max_mana: 60,
    lore: "A brave alley warrior who never backed down.",
    avatar_url: "",
    lives_remaining: 0,
    abilities: [basicAbility, specialAbility],
    user_id: "user-1",
    source_image_url: "",
    status: "MEMORIAL",
    wins: 42,
    death_date: "2024-03-15T10:00:00Z",
    personal_note: "The bravest cat I ever knew.",
    personality: "Fearless and endlessly curious.",
    created_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/memorial"]}>
      <MemorialPage />
    </MemoryRouter>,
  );
}

describe("MemorialPage (integration: page + useMemorial + Data API)", () => {
  beforeEach(() => {
    getMemorialCatsMock.mockReset();
    updateCatNoteMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("loads and renders a fully-populated fallen cat", async () => {
    const cat = makeCat();
    getMemorialCatsMock.mockResolvedValue([cat]);

    renderPage();

    // Async load: findBy* waits for the hook's fetch to resolve.
    expect(await screen.findByText("Whiskers")).toBeInTheDocument();
    expect(screen.getByText("Tabby")).toBeInTheDocument();

    // Lifetime wins.
    expect(screen.getByText("42")).toBeInTheDocument();

    // Ability names (including the special one).
    expect(screen.getByText("Phantom Pounce")).toBeInTheDocument();
    expect(screen.getByText("Swipe")).toBeInTheDocument();

    // Personality text (read-only, user-provided).
    expect(
      screen.getByText("Fearless and endlessly curious."),
    ).toBeInTheDocument();

    // Existing personal note is pre-filled in the textarea.
    const textarea = screen.getByLabelText("Personal note") as HTMLTextAreaElement;
    expect(textarea).toHaveValue("The bravest cat I ever knew.");
  });

  it("saves an edited note through updateCatNote on the happy path", async () => {
    const cat = makeCat();
    getMemorialCatsMock.mockResolvedValue([cat]);
    updateCatNoteMock.mockResolvedValue(
      makeCat({ personal_note: "Rest well, friend." }),
    );

    renderPage();

    const textarea = (await screen.findByLabelText(
      "Personal note",
    )) as HTMLTextAreaElement;

    fireEvent.change(textarea, { target: { value: "Rest well, friend." } });

    fireEvent.click(
      screen.getByRole("button", { name: /save personal note for whiskers/i }),
    );

    await waitFor(() => expect(updateCatNoteMock).toHaveBeenCalledTimes(1));
    expect(updateCatNoteMock).toHaveBeenCalledWith("cat-1", "Rest well, friend.");
  });

  it("disables Save and shows an over-limit hint when the note exceeds 500 chars", async () => {
    const cat = makeCat();
    getMemorialCatsMock.mockResolvedValue([cat]);

    renderPage();

    const textarea = (await screen.findByLabelText(
      "Personal note",
    )) as HTMLTextAreaElement;

    const tooLong = "x".repeat(501);
    fireEvent.change(textarea, { target: { value: tooLong } });

    const saveButton = screen.getByRole("button", {
      name: /save personal note for whiskers/i,
    });
    expect(saveButton).toBeDisabled();
    expect(
      screen.getByText(/must be 500 characters or fewer/i),
    ).toBeInTheDocument();

    // The guard prevents any network call.
    fireEvent.click(saveButton);
    expect(updateCatNoteMock).not.toHaveBeenCalled();
  });

  it("renders the empty state when there are no fallen cats", async () => {
    getMemorialCatsMock.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText(/no fallen cats yet/i)).toBeInTheDocument();
    expect(updateCatNoteMock).not.toHaveBeenCalled();
  });
});
