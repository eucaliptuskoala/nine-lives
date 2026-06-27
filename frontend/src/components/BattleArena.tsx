import type { ReactNode } from "react";
import type { Phase } from "../types/game";
import CatCard from "./CatCard";
import LivesDisplay from "./LivesDisplay";
import type { Class } from "../types/game";

interface BattleArenaProps {
  player: {
    name: string;
    classType: Class;
    hp: number;
    maxHp: number;
    mana: number;
    maxMana: number;
    isDefending?: boolean;
    shield?: number;
    lives: number;
  };
  enemy: {
    name: string;
    classType: Class;
    hp: number;
    maxHp: number;
    mana: number;
    maxMana: number;
    isDefending?: boolean;
    shield?: number;
  };
  phase: Phase;
  currentRound: number;
  statusText: string;
  children: ReactNode;
}

function BattleArena({
  player,
  enemy,
  phase,
  currentRound,
  statusText,
  children,
}: BattleArenaProps) {
  return (
    <div className="flex flex-col min-h-screen bg-gray-900 text-white">
      <div className="flex-1 flex flex-col max-w-2xl mx-auto w-full px-4 py-6 gap-6">
        <div className="text-center">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
            Round {currentRound}
          </span>
        </div>

        <div className="space-y-3">
          <CatCard
            name={enemy.name}
            classType={enemy.classType}
            hp={enemy.hp}
            maxHp={enemy.maxHp}
            mana={enemy.mana}
            maxMana={enemy.maxMana}
            isDefending={enemy.isDefending}
            shield={enemy.shield}
          />
        </div>

        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-sm font-medium text-gray-300">{statusText}</p>
            {phase === "ENEMY_TURN" as Phase && (
              <span className="text-xs text-gray-500">Enemy is thinking...</span>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <LivesDisplay lives={player.lives} />
          </div>
          <CatCard
            name={player.name}
            classType={player.classType}
            hp={player.hp}
            maxHp={player.maxHp}
            mana={player.mana}
            maxMana={player.maxMana}
            isDefending={player.isDefending}
            shield={player.shield}
            flip
          />
        </div>

        <div className="pt-2 pb-6">{children}</div>
      </div>
    </div>
  );
}

export default BattleArena;
