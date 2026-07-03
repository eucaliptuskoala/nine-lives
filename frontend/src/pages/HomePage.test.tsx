import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";

// --- Router: keep everything real, spy on navigate ---
const navigateMock = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

// --- Auth: driven per-test ---
vi.mock("../hooks/useSupabase", () => ({
  useAuth: vi.fn(),
  supabase: {},
}));

// --- Data API: mocked so no network happens ---
vi.mock("../api/data");

import { useAuth } from "../hooks/useSupabase";
import { getActiveGameRun } from "../api/data";
import HomePage from "./HomePage";

const useAuthMock = vi.mocked(useAuth);
const getActiveGameRunMock = vi.mocked(getActiveGameRun);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <HomePage />
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    getActiveGameRunMock.mockReset();
    getActiveGameRunMock.mockResolvedValue({ run_id: null, cat: null });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows the title and a Sign In control when logged out", () => {
    useAuthMock.mockReturnValue({ user: null, session: null, loading: false });

    renderPage();

    expect(screen.getByText("Nine Lives")).toBeInTheDocument();
    const signIn = screen.getByRole("button", { name: /sign in/i });
    signIn.click();
    expect(navigateMock).toHaveBeenCalledWith("/login");
  });

  it("shows New Game and Memorial (but not Continue) when logged in with no active run", async () => {
    useAuthMock.mockReturnValue({
      user: { id: "user-1" },
      session: null,
      loading: false,
    });

    renderPage();

    // Wait for the active-run lookup to settle.
    await waitFor(() => expect(getActiveGameRunMock).toHaveBeenCalled());

    expect(screen.getByRole("button", { name: /new game/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /memorial/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /continue/i }),
    ).not.toBeInTheDocument();

    screen.getByRole("button", { name: /new game/i }).click();
    expect(navigateMock).toHaveBeenCalledWith("/digitize");
  });

  it("offers Continue routing to the active battle when a run exists", async () => {
    useAuthMock.mockReturnValue({
      user: { id: "user-1" },
      session: null,
      loading: false,
    });
    getActiveGameRunMock.mockResolvedValue({ run_id: "run-42", cat: null });

    renderPage();

    const cont = await screen.findByRole("button", { name: /continue/i });
    cont.click();
    expect(navigateMock).toHaveBeenCalledWith("/battle/run-42");
  });

  it("shows a loading state while auth is resolving", () => {
    useAuthMock.mockReturnValue({ user: null, session: null, loading: true });

    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
  });
});
