import { motion } from "framer-motion";
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

const abilityColors: Record<string, string> = {
  [AbilityType.DMG]: "from-red-600 to-red-800 border-red-500",
  [AbilityType.HEAL]: "from-green-600 to-green-800 border-green-500",
  [AbilityType.SHIELD]: "from-cyan-600 to-cyan-800 border-cyan-500",
  [AbilityType.TRUE_DMG]: "from-purple-600 to-purple-800 border-purple-500",
  [AbilityType.AOE]: "from-orange-600 to-orange-800 border-orange-500",
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
    <div className="grid grid-cols-3 gap-2">
      <motion.button
        whileHover={disabled ? {} : { scale: 1.03 }}
        whileTap={disabled ? {} : { scale: 0.97 }}
        onClick={onAttack}
        disabled={disabled}
        className="col-span-1 px-4 py-3 rounded-lg font-semibold text-sm bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {"\u2694\uFE0F"} Attack
      </motion.button>

      <motion.button
        whileHover={disabled ? {} : { scale: 1.03 }}
        whileTap={disabled ? {} : { scale: 0.97 }}
        onClick={onDefend}
        disabled={disabled}
        className="col-span-1 px-4 py-3 rounded-lg font-semibold text-sm bg-gray-700 hover:bg-gray-600 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {"\uD83D\uDEE1\uFE0F"} Defend
      </motion.button>

      {abilities.map((ability) => {
        const cd = cooldowns[ability.id] ?? 0;
        const canAfford = mana >= ability.mana_cost;
        const canUse = cd === 0 && canAfford && !disabled;

        return (
          <motion.button
            key={ability.id}
            whileHover={canUse ? { scale: 1.03 } : {}}
            whileTap={canUse ? { scale: 0.97 } : {}}
            onClick={() => onUseAbility(ability.id)}
            disabled={!canUse}
            className={`col-span-1 px-3 py-3 rounded-lg font-semibold text-xs text-white transition-all bg-gradient-to-b ${
              ability.is_special
                ? "from-yellow-600 to-yellow-800 border border-yellow-500"
                : abilityColors[ability.type] ?? "from-gray-600 to-gray-800 border border-gray-500"
            } disabled:opacity-40 disabled:cursor-not-allowed relative`}
          >
            <span className="block leading-tight">{ability.is_special ? "\u2B50" : ""}{ability.name}</span>
            <span className="block text-[10px] opacity-75 mt-0.5">
              {ability.mana_cost} MP
              {cd > 0 ? ` \u2022 ${cd}t` : ""}
            </span>
          </motion.button>
        )},
      )}
    </div>
  );
}

export default ActionButtons;
