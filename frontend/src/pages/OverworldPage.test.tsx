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

// --- Data API: mocked so no network happens ---
vi.mock("../api/data");

import { getActiveGameRun } from "../api/data";
import OverworldPage from "./OverworldPage";

const getActiveGameRunMock = vi.mocked(getActiveGameRun);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/overworld"]}>
      <OverworldPage />
    </MemoryRouter>,
  );
}

describe("OverworldPage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    getActiveGameRunMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("resolves the run id and routes 'Next Enemy' to the active battle", async () => {
    getActiveGameRunMock.mockResolvedValue({ run_id: "run-7", cat: null });

    renderPage();

    const nextEnemy = await screen.findByRole("button", { name: /next enemy/i });
    await waitFor(() => expect(nextEnemy).toBeEnabled());
    nextEnemy.click();
    expect(navigateMock).toHaveBeenCalledWith("/battle/run-7");
  });

  it("routes 'Memorial' to the memorial page", async () => {
    getActiveGameRunMock.mockResolvedValue({ run_id: "run-7", cat: null });

    renderPage();

    const memorial = await screen.findByRole("button", { name: /memorial/i });
    memorial.click();
    expect(navigateMock).toHaveBeenCalledWith("/memorial");
  });

  it("renders 'Rest' as a disabled placeholder", async () => {
    getActiveGameRunMock.mockResolvedValue({ run_id: "run-7", cat: null });

    renderPage();

    const rest = await screen.findByRole("button", { name: /rest/i });
    expect(rest).toBeDisabled();
  });

  it("disables 'Next Enemy' and shows a message when there is no active run", async () => {
    getActiveGameRunMock.mockResolvedValue({ run_id: null, cat: null });

    renderPage();

    const nextEnemy = await screen.findByRole("button", { name: /next enemy/i });
    expect(nextEnemy).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(/no active run/i);
    nextEnemy.click();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
