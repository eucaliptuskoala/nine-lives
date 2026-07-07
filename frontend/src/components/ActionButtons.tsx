import { Button } from "@/components/ui/8bit/button";
import AbilityInfoPanel from "@/components/AbilityInfoPanel";
import InfoIcon from "@/components/InfoIcon";
import { useInfoDisclosure } from "@/hooks/useInfoDisclosure";
import { useIsTouchDevice } from "@/hooks/useIsTouchDevice";
import { canUseAbility, getAbilityInfoFields, getRemainingCooldown } from "@/lib/battleInfo";
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

interface AbilityButtonProps {
  ability: Ability;
  remainingCooldown: number;
  mana: number;
  onUseAbility: (id: string) => void;
  disabled: boolean;
}

/**
 * Renders a single ability button plus its Cooldown_Indicator,
 * hover/focus-driven Ability_Info_Panel, and (touch only) Info_Icon.
 *
 * Extracted from the `abilities.map()` loop so `useInfoDisclosure` and
 * `useIsTouchDevice` can be called once per ability without violating the
 * rules of hooks (Requirements 1, 2, 6).
 */
function AbilityButton({
  ability,
  remainingCooldown,
  mana,
  onUseAbility,
  disabled,
}: AbilityButtonProps) {
  const canUse = canUseAbility(remainingCooldown, mana, ability.mana_cost, !disabled);
  const isTouchDevice = useIsTouchDevice();
  const disclosure = useInfoDisclosure({ disabled: !canUse });

  return (
    <div className="relative col-span-1">
      <Button
        type="button"
        onClick={() => onUseAbility(ability.id)}
        disabled={!canUse}
        {...disclosure.triggerProps}
        className={`h-auto min-h-12 w-full flex-col px-3 py-3 text-[10px] leading-tight ${
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
        </span>
        {remainingCooldown > 0 && (
          <span className="mt-0.5 flex items-center gap-0.5 text-[9px] opacity-75">
            {"\u23F3"} {remainingCooldown}t
          </span>
        )}
      </Button>
      {isTouchDevice && (
        <div className="absolute -right-1 -top-1">
          <InfoIcon
            onToggle={disclosure.toggleTouch}
            aria-controls={disclosure.panelId}
            label={`Toggle info for ${ability.name}`}
          />
        </div>
      )}
      {disclosure.isOpen && (
        <AbilityInfoPanel id={disclosure.panelId} fields={getAbilityInfoFields(ability)} />
      )}
    </div>
  );
}

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

      {abilities.map((ability) => (
        <AbilityButton
          key={ability.id}
          ability={ability}
          remainingCooldown={getRemainingCooldown(cooldowns, ability.id)}
          mana={mana}
          onUseAbility={onUseAbility}
          disabled={disabled}
        />
      ))}
    </div>
  );
}

export default ActionButtons;
