import type { AbilityInfoFields } from "@/lib/battleInfo";
import { cn } from "@/lib/utils";

interface AbilityInfoPanelProps {
  /** Must equal the triggering element's `useInfoDisclosure().panelId`. */
  id: string;
  /** Shown for enemy abilities (Req 4.3); optional for player abilities since
   *  the ability button already displays the name. */
  name?: string;
  fields: AbilityInfoFields;
  className?: string;
}

/**
 * Presentational Ability_Info_Panel. Renders an already-derived
 * `AbilityInfoFields` object — never touches raw `Ability`/`EnemyAbility`
 * data itself, so the same component serves both player abilities
 * (Requirement 2) and enemy abilities (Requirement 4).
 */
function AbilityInfoPanel({ id, name, fields, className }: AbilityInfoPanelProps) {
  return (
    <div
      role="tooltip"
      id={id}
      className={cn(
        "absolute z-10 w-56 rounded-md border-2 border-border-ui bg-panel p-3 text-xs text-text-primary shadow-lg",
        className,
      )}
    >
      {name && <p className="mb-1 font-semibold">{name}</p>}
      <p className="text-text-secondary">{fields.description}</p>
      <p className="mt-1">
        <span className="font-medium">Damage:</span> {fields.dmg}
      </p>
      <p>
        <span className="font-medium">Effect:</span> {fields.effect}
      </p>
      {fields.lore !== undefined && (
        <p className="mt-1 italic text-text-secondary">{fields.lore}</p>
      )}
    </div>
  );
}

export default AbilityInfoPanel;
