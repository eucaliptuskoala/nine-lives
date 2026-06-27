import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Phase } from "../types/game";
import type { GameState } from "../types/game";
import { useGameState } from "../hooks/useGameState";
import BattleArena from "../components/BattleArena";
import ActionButtons from "../components/ActionButtons";
import FarewellScreen from "../components/FarewellScreen";
import { MOCK_CAT } from "../data/mockCat";

const STORAGE_KEY = "nl-battle-state";

function BattlePage() {
  const navigate = useNavigate();
  const { state, initRound, attack, defend, useAbility, resolveEnemyTurn, setState } =
    useGameState();
  const [statusText, setStatusText] = useState("Prepare for battle!");
  const [actionCooldown, setActionCooldown] = useState(false);
  const cooldownTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const isGameOver = state !== null && state.lives_remaining <= 0 && state.player_hp <= 0;
  const canAct = state?.phase === Phase.PLAYER_TURN && !actionCooldown;

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as GameState;
        setState(parsed);
        setStatusText("Battle resumed!");
        return;
      } catch { /* fall through to init */ }
    }
    initRound(
      MOCK_CAT.current_hp,
      MOCK_CAT.max_hp,
      MOCK_CAT.mana,
      MOCK_CAT.max_mana,
      MOCK_CAT.lives_remaining,
      1
    );
  }, []);

  useEffect(() => {
    if (state && !isGameOver) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  }, [state, isGameOver]);

  useEffect(() => {
    if (state?.phase === Phase.ENEMY_TURN) {
      setStatusText("Enemy is attacking...");
      const timer = setTimeout(() => {
        resolveEnemyTurn();
      }, 1200);
      return () => clearTimeout(timer);
    }
    if (state?.phase === Phase.PLAYER_TURN && !actionCooldown) {
      setStatusText("Your turn!");
    }
  }, [state?.phase, actionCooldown]);

  const startCooldown = useCallback(() => {
    setActionCooldown(true);
    if (cooldownTimer.current) clearTimeout(cooldownTimer.current);
    cooldownTimer.current = setTimeout(() => {
      setActionCooldown(false);
    }, 1200);
  }, []);

  const handleAttack = useCallback(() => {
    if (!canAct) return;
    setStatusText("You attack!");
    attack();
    startCooldown();
  }, [canAct, attack, startCooldown]);

  const handleDefend = useCallback(() => {
    if (!canAct) return;
    setStatusText("You brace for impact!");
    defend();
    startCooldown();
  }, [canAct, defend, startCooldown]);

  const handleUseAbility = useCallback(
    (abilityId: string) => {
      if (!canAct) return;
      const ability = MOCK_CAT.abilities.find((a) => a.id === abilityId);
      if (!ability) return;
      setStatusText(`You use ${ability.name}!`);
      useAbility(abilityId, MOCK_CAT.abilities);
      startCooldown();
    },
    [canAct, useAbility, startCooldown]
  );

  const handleClearStorage = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    navigate("/memorial");
  }, [navigate]);

  if (isGameOver) {
    return (
      <FarewellScreen
        catName={MOCK_CAT.name}
        onGoToMemorial={handleClearStorage}
      />
    );
  }

  if (!state) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <BattleArena
      player={{
        name: MOCK_CAT.name,
        classType: MOCK_CAT.class,
        hp: state.player_hp,
        maxHp: state.player_max_hp,
        mana: state.player_mana,
        maxMana: state.player_max_mana,
        isDefending: state.player_is_defending,
        shield: state.player_shield,
        lives: state.lives_remaining,
      }}
      enemy={{
        name: state.enemy.name,
        classType: "STRENGTH",
        hp: state.enemy.hp,
        maxHp: state.enemy.max_hp,
        mana: state.enemy.mana,
        maxMana: state.enemy.max_mana,
      }}
      phase={state.phase}
      currentRound={state.current_round}
      statusText={statusText}
    >
      <ActionButtons
        abilities={MOCK_CAT.abilities}
        cooldowns={state.player_ability_cooldowns}
        mana={state.player_mana}
        onAttack={handleAttack}
        onDefend={handleDefend}
        onUseAbility={handleUseAbility}
        disabled={!canAct}
      />
    </BattleArena>
  );
}

export default BattlePage;
