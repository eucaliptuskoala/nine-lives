import { useId, useState } from "react";
import { Button } from "@/components/ui/8bit/button";
import { Textarea } from "@/components/ui/8bit/textarea";
import { Card } from "@/components/ui/8bit/card";
import { NOTE_MAX_LENGTH } from "../hooks/useMemorial";
import type { Cat, Class } from "../types/game";

interface MemorialCatCardProps {
  cat: Cat;
  onSaveNote: (catId: string, note: string) => Promise<void>;
}

const classColors: Record<Class, string> = {
  STRENGTH: "text-class-strength",
  AGILITY: "text-class-agility",
  INTELLIGENCE: "text-class-intelligence",
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
    <Card
      font="normal"
      className="bg-panel/60 border-border-ui text-text-secondary"
    >
      <div className="flex flex-col gap-4 p-5">
      {/* Header: avatar + identity */}
      <div className="flex items-center gap-4">
        <div className="w-20 h-20 rounded-full bg-elevated flex items-center justify-center text-3xl shrink-0 border-2 border-border-ui overflow-hidden">
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
          <h2 className="text-xl font-bold text-text-primary truncate">{cat.name}</h2>
          <p className="text-sm text-text-secondary">{cat.breed}</p>
          <span className={`text-xs font-medium ${classColors[cat.class]}`}>
            {cat.class}
          </span>
        </div>
      </div>

      {/* Final stats */}
      <div>
        <h3 className="text-sm font-semibold text-text-secondary mb-2">Final stats</h3>
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-sm">
          <div className="flex justify-between gap-2">
            <dt className="text-text-secondary">Max HP</dt>
            <dd className="font-medium text-text-primary">{cat.max_hp}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-secondary">Damage</dt>
            <dd className="font-medium text-text-primary">{cat.dmg}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-secondary">Defence</dt>
            <dd className="font-medium text-text-primary">{cat.defence}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-secondary">Speed</dt>
            <dd className="font-medium text-text-primary">{cat.spd}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-secondary">Max Mana</dt>
            <dd className="font-medium text-text-primary">{cat.max_mana}</dd>
          </div>
        </dl>
      </div>

      {/* Abilities */}
      <div>
        <h3 className="text-sm font-semibold text-text-secondary mb-2">Abilities</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {cat.abilities.map((ability) => (
            <li key={ability.id} className="flex items-center gap-2">
              <span className="text-text-primary">{ability.name}</span>
              <span className="text-xs text-text-secondary">({ability.type})</span>
              {ability.is_special && (
                <span className="text-xs font-medium text-rarity-special">
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
          <h3 className="text-sm font-semibold text-text-secondary mb-1">Lore</h3>
          <p className="text-sm text-text-secondary italic whitespace-pre-line">
            {cat.lore}
          </p>
        </div>
      )}

      {/* Personality (read-only, user-provided) */}
      {cat.personality && (
        <div>
          <h3 className="text-sm font-semibold text-text-secondary mb-1">
            Personality
          </h3>
          <p className="text-sm text-text-secondary whitespace-pre-line">
            {cat.personality}
          </p>
        </div>
      )}

      {/* Death date + wins */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm border-t border-border-ui pt-3">
        <div className="flex gap-2">
          <span className="text-text-secondary">Fell on</span>
          <span className="font-medium text-text-primary">
            {formatDeathDate(cat.death_date)}
          </span>
        </div>
        <div className="flex gap-2">
          <span className="text-text-secondary">Lifetime wins</span>
          <span className="font-medium text-text-primary">{cat.wins}</span>
        </div>
      </div>

      {/* Personal note editor */}
      <div className="flex flex-col gap-1 border-t border-border-ui pt-3">
        <label htmlFor={noteId} className="text-sm font-semibold text-text-secondary">
          Personal note
        </label>
        <Textarea
          id={noteId}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          disabled={saving}
          placeholder="Write a few words to remember them by."
          font="normal"
          className="resize-none bg-app text-sm text-text-primary"
        />
        <div className="flex items-center justify-between">
          <span
            className={`text-xs ${tooLong ? "text-hp" : "text-text-secondary"}`}
          >
            {note.length}/{NOTE_MAX_LENGTH}
          </span>
          <Button
            type="button"
            onClick={handleSave}
            disabled={!canSave}
            aria-label={`Save personal note for ${cat.name}`}
            className="h-auto bg-accent hover:bg-accent/90 px-4 py-1.5 text-[10px] text-app"
          >
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
        {tooLong && (
          <span className="text-xs text-hp">
            Note must be {NOTE_MAX_LENGTH} characters or fewer.
          </span>
        )}
      </div>
      </div>
    </Card>
  );
}

export default MemorialCatCard;
