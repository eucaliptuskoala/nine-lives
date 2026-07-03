import { useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";
import { Input } from "@/components/ui/8bit/input";
import { Textarea } from "@/components/ui/8bit/textarea";
import { useAuth } from "../hooks/useSupabase";
import { createGameRun } from "../api/data";
import { uploadCatPhoto } from "../api/digitize";
import { formatFileSize, validateImageFile } from "../utils/storage";

const MAX_NAME_LENGTH = 100;
const MAX_PERSONALITY_LENGTH = 500;

type DigitizeStatus = "idle" | "processing" | "error";

/**
 * DigitizePage — collects a cat name, photo, and optional personality
 * description, creates a game run, uploads the photo to the digitize endpoint,
 * and navigates to the battle once the cat has been generated.
 *
 * Auth is obtained via `useAuth()` only; all data flows through the backend API.
 *
 * Related: Requirements 1.1–1.9, 7.1, 26.1, 26.2, 27.1–27.4
 */
function DigitizePage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [catName, setCatName] = useState("");
  const [personality, setPersonality] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const [status, setStatus] = useState<DigitizeStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // The run id is created once and reused across retries so a failed attempt
  // doesn't spawn a second game run (Req 1.9, 26.2).
  const [runId, setRunId] = useState<string | null>(null);

  const trimmedName = catName.trim();
  const nameTooLong = catName.length > MAX_NAME_LENGTH;
  const personalityTooLong = personality.length > MAX_PERSONALITY_LENGTH;

  const canSubmit = useMemo(
    () =>
      trimmedName.length > 0 &&
      !nameTooLong &&
      file !== null &&
      fileError === null &&
      !personalityTooLong,
    [trimmedName, nameTooLong, file, fileError, personalityTooLong],
  );

  const isProcessing = status === "processing";

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;

    if (!selected) {
      setFile(null);
      setFileError(null);
      return;
    }

    const validation = validateImageFile(selected);
    if (!validation.valid) {
      setFile(null);
      setFileError(validation.error ?? "Invalid file.");
      return;
    }

    setFile(selected);
    setFileError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canSubmit || !file) return;

    if (!user) {
      setStatus("error");
      setErrorMessage("You must be signed in to digitize a cat.");
      return;
    }

    setStatus("processing");
    setErrorMessage(null);

    try {
      // Reuse an existing run id on retry; only create a new run the first time.
      let currentRunId = runId;
      if (!currentRunId) {
        const run = await createGameRun();
        currentRunId = run.run_id;
        setRunId(currentRunId);
      }

      await uploadCatPhoto(file, {
        gameRunId: currentRunId,
        userId: user.id,
        catName: trimmedName,
        personality: personality.trim() || undefined,
      });

      navigate(`/battle/${currentRunId}`);
    } catch (err) {
      setStatus("error");
      setErrorMessage(
        err instanceof Error
          ? err.message
          : "Something went wrong while digitizing your cat. Please try again.",
      );
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6 px-4 py-10">
      <div className="w-full max-w-md flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="retro text-2xl font-bold">Digitize Your Cat</h1>
          <p className="text-gray-500">
            Upload a photo and give your cat a name to enter the arena.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Cat name */}
          <label className="flex flex-col gap-2 text-sm font-medium">
            Cat name
            <Input
              type="text"
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              maxLength={MAX_NAME_LENGTH + 20}
              required
              disabled={isProcessing}
              placeholder="e.g. Sir Whiskers"
              font="normal"
            />
            {nameTooLong && (
              <span className="text-sm text-red-600">
                Name must be {MAX_NAME_LENGTH} characters or fewer.
              </span>
            )}
          </label>

          {/* Photo */}
          <label className="flex flex-col gap-1 text-sm font-medium">
            Photo
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileChange}
              disabled={isProcessing}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-indigo-50 file:px-3 file:py-1 file:text-indigo-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
            />
            {fileError && (
              <span role="alert" className="text-sm text-red-600">
                {fileError}
              </span>
            )}
            {file && !fileError && (
              <span className="text-sm text-gray-500">
                {file.name} ({formatFileSize(file.size)})
              </span>
            )}
          </label>

          {/* Personality */}
          <label className="flex flex-col gap-2 text-sm font-medium">
            Personality (optional)
            <Textarea
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
              rows={4}
              disabled={isProcessing}
              placeholder="Describe your cat's personality to shape their stats and abilities."
              font="normal"
              className="resize-none"
            />
            <span
              className={`self-end text-xs ${
                personalityTooLong ? "text-red-600" : "text-gray-400"
              }`}
            >
              {personality.length}/{MAX_PERSONALITY_LENGTH}
            </span>
            {personalityTooLong && (
              <span className="text-sm text-red-600">
                Personality must be {MAX_PERSONALITY_LENGTH} characters or fewer.
              </span>
            )}
          </label>

          {errorMessage && (
            <p role="alert" className="text-sm text-red-600">
              {errorMessage}
            </p>
          )}

          <Button
            type="submit"
            disabled={!canSubmit || isProcessing}
            className="mt-2 h-auto bg-indigo-600 px-4 py-2 text-[10px] text-white"
          >
            {isProcessing ? (
              <span className="inline-flex items-center gap-2">
                Digitizing...
                <span className="inline-flex gap-0.5" aria-hidden="true">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="inline-block h-1.5 w-1.5 bg-white"
                      animate={{ opacity: [0.2, 1, 0.2] }}
                      transition={{
                        duration: 0.8,
                        repeat: Infinity,
                        delay: i * 0.15,
                      }}
                    />
                  ))}
                </span>
              </span>
            ) : status === "error" ? (
              "Retry"
            ) : (
              "Digitize"
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}

export default DigitizePage;
