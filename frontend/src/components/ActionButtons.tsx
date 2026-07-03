import { Button } from "@/components/ui/8bit/button";
import type { Ability } from "../types/game";
import { AbilityType } from "../types/game";

interface ActionButtonsProps {
  abilities: Ability[];
  cooldowns: Record<string, number>;
  mana: number;
  onAttack: () => void;
  onDefend: () => void;
  onUseAbility: (id: string) => void;
  disabled: boolean;
}

// Retro accent colours per ability type. These override the 8bit Button's
// default `bg-foreground` fill while keeping its pixelated frame.
const abilityColors: Record<string, string> = {
  [AbilityType.DMG]: "bg-red-700 text-white",
  [AbilityType.HEAL]: "bg-green-700 text-white",
  [AbilityType.SHIELD]: "bg-cyan-700 text-white",
  [AbilityType.TRUE_DMG]: "bg-purple-700 text-white",
  [AbilityType.AOE]: "bg-orange-700 text-white",
};

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
        className="col-span-1 h-auto min-h-12 px-4 py-3 text-xs bg-gray-700 text-white"
      >
        {"\u2694\uFE0F"} Attack
      </Button>

      <Button
        type="button"
        onClick={onDefend}
        disabled={disabled}
        className="col-span-1 h-auto min-h-12 px-4 py-3 text-xs bg-gray-700 text-white"
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
              ability.is_special
                ? "bg-yellow-600 text-white"
                : abilityColors[ability.type] ?? "bg-gray-700 text-white"
            }`}
          >
            <span className="block leading-tight">
              {ability.is_special ? "\u2B50" : ""}
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
