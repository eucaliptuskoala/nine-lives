import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import type { Cat } from "../types/game";
import type { CreateGameRunResponse } from "../api/data";

// --- Router: keep everything real, spy on navigate ---
const navigateMock = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigateMock };
});

// --- Auth: DigitizePage only reads `user`. storage.ts also imports `supabase`
// from this module, but the pure helpers we exercise (validateImageFile /
// formatFileSize) never touch it, so a stub client is fine. ---
vi.mock("../hooks/useSupabase", () => ({
  useAuth: () => ({ user: { id: "user-1" }, session: null, loading: false }),
  supabase: {},
}));

// --- API clients: mocked so no network happens ---
vi.mock("../api/data");
vi.mock("../api/digitize");

import { createGameRun } from "../api/data";
import { uploadCatPhoto } from "../api/digitize";
import DigitizePage from "./DigitizePage";

const createGameRunMock = vi.mocked(createGameRun);
const uploadCatPhotoMock = vi.mocked(uploadCatPhoto);

const runResponse: CreateGameRunResponse = {
  run_id: "run-123",
  status: "DIGITIZING",
};

// Minimal Cat resolved on a successful upload. The component ignores the
// returned value (it navigates to the run), so only shape matters for typing.
const uploadedCat = { id: "cat-1", name: "Whiskers" } as unknown as Cat;

/** A valid PNG File that passes validateImageFile (type + extension + size). */
function makeValidPhoto(): File {
  return new File([new Uint8Array([1, 2, 3, 4])], "cat.png", {
    type: "image/png",
  });
}

/** An oversized (>10MB) PNG — right type/extension but fails the size check. */
function makeOversizedPhoto(): File {
  const file = new File([new Uint8Array([1, 2, 3, 4])], "cat.png", {
    type: "image/png",
  });
  Object.defineProperty(file, "size", { value: 11 * 1024 * 1024 });
  return file;
}

/** A wrong-type file (text) that fails the MIME/extension check. */
function makeWrongTypePhoto(): File {
  return new File([new Uint8Array([1, 2, 3, 4])], "cat.txt", {
    type: "text/plain",
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/digitize"]}>
      <DigitizePage />
    </MemoryRouter>,
  );
}

function getFileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("file input not found");
  return input;
}

function getNameInput(): HTMLInputElement {
  return screen.getByRole("textbox", { name: /cat name/i }) as HTMLInputElement;
}

function getSubmitButton(): HTMLButtonElement {
  return screen.getByRole("button", {
    name: /digitize|retry|digitizing/i,
  }) as HTMLButtonElement;
}

describe("DigitizePage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    createGameRunMock.mockReset();
    uploadCatPhotoMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows a validation error and keeps submit disabled for an invalid file", () => {
    const { container } = renderPage();

    // A valid name alone should not enable submit without a valid photo.
    fireEvent.change(getNameInput(), { target: { value: "Mittens" } });

    // Oversized file (>10MB) — rejected by validateImageFile.
    fireEvent.change(getFileInput(container), {
      target: { files: [makeOversizedPhoto()] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(/too large/i);
    expect(getSubmitButton()).toBeDisabled();

    // Wrong file type is likewise rejected.
    fireEvent.change(getFileInput(container), {
      target: { files: [makeWrongTypePhoto()] },
    });

    expect(screen.getByRole("alert")).toHaveTextContent(/invalid file type/i);
    expect(getSubmitButton()).toBeDisabled();

    expect(createGameRunMock).not.toHaveBeenCalled();
    expect(uploadCatPhotoMock).not.toHaveBeenCalled();
  });

  it("keeps submit disabled when the name is empty even with a valid photo", () => {
    const { container } = renderPage();

    fireEvent.change(getFileInput(container), {
      target: { files: [makeValidPhoto()] },
    });

    // Valid photo, but no name yet.
    expect(getSubmitButton()).toBeDisabled();

    // Whitespace-only name is treated as empty.
    fireEvent.change(getNameInput(), { target: { value: "   " } });
    expect(getSubmitButton()).toBeDisabled();

    // A real name finally enables the button.
    fireEvent.change(getNameInput(), { target: { value: "Mittens" } });
    expect(getSubmitButton()).toBeEnabled();
  });

  it("creates a run, uploads the photo, then navigates on the happy path", async () => {
    createGameRunMock.mockResolvedValue(runResponse);
    uploadCatPhotoMock.mockResolvedValue(uploadedCat);

    const { container } = renderPage();

    const photo = makeValidPhoto();
    fireEvent.change(getNameInput(), { target: { value: "Mittens" } });
    fireEvent.change(screen.getByRole("textbox", { name: /personality/i }), {
      target: { value: "Grumpy but loyal" },
    });
    fireEvent.change(getFileInput(container), { target: { files: [photo] } });

    fireEvent.click(getSubmitButton());

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/battle/run-123"));

    expect(createGameRunMock).toHaveBeenCalledTimes(1);
    expect(uploadCatPhotoMock).toHaveBeenCalledTimes(1);
    expect(uploadCatPhotoMock).toHaveBeenCalledWith(photo, {
      gameRunId: "run-123",
      userId: "user-1",
      catName: "Mittens",
      personality: "Grumpy but loyal",
    });
  });

  it("passes personality as undefined when left blank", async () => {
    createGameRunMock.mockResolvedValue(runResponse);
    uploadCatPhotoMock.mockResolvedValue(uploadedCat);

    const { container } = renderPage();

    const photo = makeValidPhoto();
    fireEvent.change(getNameInput(), { target: { value: "Mittens" } });
    fireEvent.change(getFileInput(container), { target: { files: [photo] } });

    fireEvent.click(getSubmitButton());

    await waitFor(() => expect(uploadCatPhotoMock).toHaveBeenCalledTimes(1));
    expect(uploadCatPhotoMock).toHaveBeenCalledWith(photo, {
      gameRunId: "run-123",
      userId: "user-1",
      catName: "Mittens",
      personality: undefined,
    });
  });

  it("reuses the run id on retry after an upload failure", async () => {
    createGameRunMock.mockResolvedValue(runResponse);
    uploadCatPhotoMock.mockRejectedValueOnce(new Error("Digitization failed (500)"));

    const { container } = renderPage();

    const photo = makeValidPhoto();
    fireEvent.change(getNameInput(), { target: { value: "Mittens" } });
    fireEvent.change(getFileInput(container), { target: { files: [photo] } });

    // First attempt: run is created, upload rejects, error is surfaced.
    fireEvent.click(getSubmitButton());

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/digitization failed/i);
    expect(createGameRunMock).toHaveBeenCalledTimes(1);
    expect(uploadCatPhotoMock).toHaveBeenCalledTimes(1);

    // Second attempt: upload now succeeds.
    uploadCatPhotoMock.mockResolvedValueOnce(uploadedCat);
    fireEvent.click(getSubmitButton());

    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/battle/run-123"));

    // Retry must NOT create a new run — it reuses the stored run id.
    expect(createGameRunMock).toHaveBeenCalledTimes(1);
    expect(uploadCatPhotoMock).toHaveBeenCalledTimes(2);
  });
});
