import type { ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Phase } from "../types/game";
import CatCard from "./CatCard";
import LivesDisplay from "./LivesDisplay";
import { Card } from "@/components/ui/8bit/card";
import type { Class } from "../types/game";
import type {
  AbilityInfoFields,
  EnemyAbilityListEntry,
  EnemyStatFields,
  PlayerStatFields,
} from "@/lib/battleInfo";

interface BattleArenaProps {
  player: {
    name: string;
    avatarUrl?: string;
    classType: Class;
    hp: number;
    maxHp: number;
    mana: number;
    maxMana: number;
    isDefending?: boolean;
    shield?: number;
    lives: number;
    /** Requirement 3.1: enables the player avatar's Stat_Info_Panel trigger when provided. */
    statPanel?: PlayerStatFields;
    /** Overrides the player Stat_Info_Panel's title; defaults to `name`. */
    statPanelTitle?: string;
  };
  enemy: {
    name: string;
    avatarUrl?: string;
    classType: Class;
    hp: number;
    maxHp: number;
    mana: number;
    maxMana: number;
    isDefending?: boolean;
    shield?: number;
    /** Requirement 5.1: enables the enemy avatar's Stat_Info_Panel trigger when provided. */
    statPanel?: EnemyStatFields;
    /** Overrides the enemy Stat_Info_Panel's title; defaults to `name`. */
    statPanelTitle?: string;
    /** Requirement 4.1: enables the Enemy_Ability_List when provided. */
    abilityList?: EnemyAbilityListEntry[];
    /** Requirement 4.3: keyed by ability id, sourced via `getEnemyAbilityInfoFields`. */
    abilityFieldsById?: Record<string, AbilityInfoFields>;
    /** Requirement 5: enables the Pinned mechanic on the enemy avatar's Stat_Info_Panel. Default false. */
    pinnable?: boolean;
  };
  phase: Phase;
  currentRound: number;
  statusText: string;
  isResolving?: boolean;
  children: ReactNode;
}

function BattleArena({
  player,
  enemy,
  phase,
  currentRound,
  statusText,
  isResolving = false,
  children,
}: BattleArenaProps) {
  return (
    <div className="flex flex-col min-h-screen bg-app text-text-primary">
      <div className="flex-1 flex flex-col max-w-2xl mx-auto w-full px-3 sm:px-4 py-4 sm:py-6 gap-4 sm:gap-6">
        <div className="text-center">
          <span className="retro text-[10px] font-medium text-text-secondary uppercase tracking-wider">
            Round {currentRound}
          </span>
        </div>

        <div className="space-y-3">
          <CatCard
            name={enemy.name}
            avatarUrl={enemy.avatarUrl}
            classType={enemy.classType}
            hp={enemy.hp}
            maxHp={enemy.maxHp}
            mana={enemy.mana}
            maxMana={enemy.maxMana}
            isDefending={enemy.isDefending}
            shield={enemy.shield}
            statPanel={enemy.statPanel}
            statPanelTitle={enemy.statPanelTitle}
            abilityList={enemy.abilityList}
            abilityFieldsById={enemy.abilityFieldsById}
            pinnable={enemy.pinnable}
          />
        </div>

        <div className="flex-1 flex items-center justify-center">
          <Card
            font="normal"
            className="bg-panel/60 border-border-ui text-text-secondary w-full sm:w-auto"
          >
            <div className="px-6 py-4 text-center">
              <AnimatePresence mode="wait">
                  <motion.p
                    key={statusText}
                    role="status"
                    aria-live="polite"
                    className="text-sm font-medium text-text-secondary"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.2 }}
                  >
                    {statusText}
                  </motion.p>
              </AnimatePresence>
              {isResolving && (
                <span className="mt-1 inline-flex gap-1" aria-hidden="true">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="inline-block h-1.5 w-1.5 bg-text-secondary"
                      animate={{ opacity: [0.2, 1, 0.2] }}
                      transition={{
                        duration: 0.8,
                        repeat: Infinity,
                        delay: i * 0.15,
                      }}
                    />
                  ))}
                </span>
              )}
              {phase === "ENEMY_TURN" as Phase && (
                <span className="text-xs text-text-disabled">Enemy is thinking...</span>
              )}
            </div>
          </Card>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <LivesDisplay lives={player.lives} />
          </div>
          <CatCard
            name={player.name}
            avatarUrl={player.avatarUrl}
            classType={player.classType}
            hp={player.hp}
            maxHp={player.maxHp}
            mana={player.mana}
            maxMana={player.maxMana}
            isDefending={player.isDefending}
            shield={player.shield}
            statPanel={player.statPanel}
            statPanelTitle={player.statPanelTitle}
            flip
          />
        </div>

        <div className="pt-2 pb-6">{children}</div>
      </div>
    </div>
  );
}

export default BattleArena;
