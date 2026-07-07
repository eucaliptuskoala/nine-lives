import { Button } from "@/components/ui/8bit/button";
import type { Ability } from "../types/game";

interface ActionButtonsProps {
  abilities: Ability[];
  cooldowns: Record<string, number>;
  mana: number;
  onAttack: () => void;
  onDefend: () => void;
  onUseAbility: (id: string) => void;
  disabled: boolean;
}

// Battle palette (Task 16.3). A regular ability uses the Ability green; a
// special/ultimate ability uses the Ultimate gold. These override the 8bit
// Button's default `bg-foreground` fill while keeping its pixelated frame.
const ABILITY_CLASS = "bg-ability hover:bg-ability-hover text-text-primary";
const ULTIMATE_CLASS = "bg-ultimate hover:bg-ultimate-hover text-text-primary";

function ActionButtons({
  abilities,
  cooldowns,
  mana,
  onAttack,
  onDefend,
  onUseAbility,
  disabled,
}: ActionButtonsProps) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <Button
        type="button"
        onClick={onAttack}
        disabled={disabled}
        className="col-span-1 h-auto min-h-12 px-4 py-3 text-xs bg-attack hover:bg-attack-hover text-text-primary"
      >
        {"\u2694\uFE0F"} Attack
      </Button>

      <Button
        type="button"
        onClick={onDefend}
        disabled={disabled}
        className="col-span-1 h-auto min-h-12 px-4 py-3 text-xs bg-defend hover:bg-defend-hover text-text-primary"
      >
        {"\uD83D\uDEE1\uFE0F"} Defend
      </Button>

      {abilities.map((ability) => {
        const cd = cooldowns[ability.id] ?? 0;
        const canAfford = mana >= ability.mana_cost;
        const canUse = cd === 0 && canAfford && !disabled;

        return (
          <Button
            key={ability.id}
            type="button"
            onClick={() => onUseAbility(ability.id)}
            disabled={!canUse}
            className={`col-span-1 h-auto min-h-12 flex-col px-3 py-3 text-[10px] leading-tight ${
              ability.is_special ? ULTIMATE_CLASS : ABILITY_CLASS
            }`}
          >
            <span className="block leading-tight">
              {ability.is_special ? (
                <span className="text-rarity-special">{"\u2B50"}</span>
              ) : (
                ""
              )}
              {ability.name}
            </span>
            <span className="block text-[9px] opacity-75 mt-0.5">
              {ability.mana_cost} MP
              {cd > 0 ? ` \u2022 ${cd}t` : ""}
            </span>
          </Button>
        );
      })}
    </div>
  );
}

export default ActionButtons;
