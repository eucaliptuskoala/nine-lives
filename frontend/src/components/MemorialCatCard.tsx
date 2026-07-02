import { useId, useState } from "react";
import type { Cat, Class } from "../types/game";

interface MemorialCatCardProps {
  cat: Cat;
  onSaveNote: (catId: string, note: string) => Promise<void>;
}

const NOTE_MAX_LENGTH = 500;

const classColors: Record<Class, string> = {
  STRENGTH: "text-red-400",
  AGILITY: "text-green-400",
  INTELLIGENCE: "text-blue-400",
};

/** Format an ISO date string into a readable date, tolerating null / invalid input. */
function formatDeathDate(value: string | null): string {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown";
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/**
 * A dedicated card for a fallen (MEMORIAL) cat. Unlike `CatCard`, it shows
 * final stats as static text (no live HP/mana bars), lore, death date, wins,
 * the user-provided personality, and an editable personal note.
 */
function MemorialCatCard({ cat, onSaveNote }: MemorialCatCardProps) {
  const [note, setNote] = useState<string>(cat.personal_note ?? "");
  const [saving, setSaving] = useState(false);

  const noteId = useId();
  const tooLong = note.length > NOTE_MAX_LENGTH;
  const canSave = !saving && !tooLong;

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    try {
      await onSaveNote(cat.id, note);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-5 rounded-xl bg-gray-800/60 border border-gray-700 text-gray-200">
      {/* Header: avatar + identity */}
      <div className="flex items-center gap-4">
        <div className="w-20 h-20 rounded-full bg-gray-700 flex items-center justify-center text-3xl shrink-0 border-2 border-gray-600 overflow-hidden">
          {cat.avatar_url ? (
            <img
              src={cat.avatar_url}
              alt={`${cat.name} avatar`}
              className="w-full h-full object-cover"
            />
          ) : (
            <span role="img" aria-label="cat">
              {"\uD83D\uDC31"}
            </span>
          )}
        </div>
        <div className="min-w-0">
          <h2 className="text-xl font-bold text-white truncate">{cat.name}</h2>
          <p className="text-sm text-gray-400">{cat.breed}</p>
          <span className={`text-xs font-medium ${classColors[cat.class]}`}>
            {cat.class}
          </span>
        </div>
      </div>

      {/* Final stats */}
      <div>
        <h3 className="text-sm font-semibold text-gray-300 mb-2">Final stats</h3>
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-sm">
          <div className="flex justify-between gap-2">
            <dt className="text-gray-400">Max HP</dt>
            <dd className="font-medium text-white">{cat.max_hp}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-400">Damage</dt>
            <dd className="font-medium text-white">{cat.dmg}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-400">Defence</dt>
            <dd className="font-medium text-white">{cat.defence}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-400">Speed</dt>
            <dd className="font-medium text-white">{cat.spd}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-gray-400">Max Mana</dt>
            <dd className="font-medium text-white">{cat.max_mana}</dd>
          </div>
        </dl>
      </div>

      {/* Abilities */}
      <div>
        <h3 className="text-sm font-semibold text-gray-300 mb-2">Abilities</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {cat.abilities.map((ability) => (
            <li key={ability.id} className="flex items-center gap-2">
              <span className="text-white">{ability.name}</span>
              <span className="text-xs text-gray-400">({ability.type})</span>
              {ability.is_special && (
                <span className="text-xs font-medium text-amber-400">
                  {"\u2605"} Special
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Lore */}
      {cat.lore && (
        <div>
          <h3 className="text-sm font-semibold text-gray-300 mb-1">Lore</h3>
          <p className="text-sm text-gray-300 italic whitespace-pre-line">
            {cat.lore}
          </p>
        </div>
      )}

      {/* Personality (read-only, user-provided) */}
      {cat.personality && (
        <div>
          <h3 className="text-sm font-semibold text-gray-300 mb-1">
            Personality
          </h3>
          <p className="text-sm text-gray-300 whitespace-pre-line">
            {cat.personality}
          </p>
        </div>
      )}

      {/* Death date + wins */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm border-t border-gray-700 pt-3">
        <div className="flex gap-2">
          <span className="text-gray-400">Fell on</span>
          <span className="font-medium text-white">
            {formatDeathDate(cat.death_date)}
          </span>
        </div>
        <div className="flex gap-2">
          <span className="text-gray-400">Lifetime wins</span>
          <span className="font-medium text-white">{cat.wins}</span>
        </div>
      </div>

      {/* Personal note editor */}
      <div className="flex flex-col gap-1 border-t border-gray-700 pt-3">
        <label htmlFor={noteId} className="text-sm font-semibold text-gray-300">
          Personal note
        </label>
        <textarea
          id={noteId}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          disabled={saving}
          placeholder="Write a few words to remember them by."
          className="resize-none rounded-md border border-gray-600 bg-gray-900 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <div className="flex items-center justify-between">
          <span
            className={`text-xs ${tooLong ? "text-red-400" : "text-gray-400"}`}
          >
            {note.length}/{NOTE_MAX_LENGTH}
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={!canSave}
            aria-label={`Save personal note for ${cat.name}`}
            className="rounded-md bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
        {tooLong && (
          <span className="text-xs text-red-400">
            Note must be {NOTE_MAX_LENGTH} characters or fewer.
          </span>
        )}
      </div>
    </div>
  );
}

export default MemorialCatCard;
