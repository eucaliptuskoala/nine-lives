import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate, useParams } from "react-router-dom";
import { Class, Phase } from "../types/game";
import { useGameState } from "../hooks/useGameState";
import { useAudio } from "../hooks/useAudio";
import { getEnemySpriteUrl } from "../utils/enemySprites";
import {
  getEnemyAbilityInfoFields,
  getEnemyStatFields,
  getPlayerStatFields,
  toEnemyAbilityList,
} from "@/lib/battleInfo";
import BattleArena from "../components/BattleArena";
import ActionButtons from "../components/ActionButtons";
import FarewellScreen from "../components/FarewellScreen";
import { Button } from "@/components/ui/8bit/button";

function PixelSpinner() {
  return (
    <div className="flex items-center justify-center gap-1.5" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block h-3 w-3 bg-text-secondary"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: i * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

function BattlePage() {
  const navigate = useNavigate();
  const { runId } = useParams<{ runId: string }>();
  const {
    gameState,
    cat,
    isLoading,
    error,
    revival,
    gameOver,
    sessionExpired,
    runEnded,
    events,
    startBattle,
    submitAction,
  } = useGameState();
  const { playMoveSound } = useAudio();

  const handleAttack = useCallback(() => {
    playMoveSound("attack");
    submitAction("attack");
  }, [playMoveSound, submitAction]);

  const handleDefend = useCallback(() => {
    playMoveSound("defend");
    submitAction("defend");
  }, [playMoveSound, submitAction]);

  const handleAbility = useCallback(
    (abilityId: string) => {
      const ability = cat?.abilities.find((a) => a.id === abilityId);
      playMoveSound(ability?.is_special ? "ultimate" : "ability");
      submitAction("ability", abilityId);
    },
    [cat, playMoveSound, submitAction],
  );

  const [victoryRound, setVictoryRound] = useState<number | null>(null);
  const prevRoundRef = useRef<number | null>(null);

  useEffect(() => {
    if (runId) {
      startBattle(runId);
    }
  }, [runId, startBattle]);

  const currentRound = gameState?.current_round ?? null;
  useEffect(() => {
    if (currentRound == null) return;
    const prev = prevRoundRef.current;
    prevRoundRef.current = currentRound;
    if (prev != null && currentRound > prev) {
      setVictoryRound(currentRound);
    }
  }, [currentRound]);

  const handleVictoryDismiss = () => {
    setVictoryRound(null);
    navigate("/overworld");
  };

  // Session expired mid-battle (401) — redirect to login.
  useEffect(() => {
    if (sessionExpired) {
      navigate("/login", { state: { from: `/battle/${runId}` } });
    }
  }, [sessionExpired, navigate, runId]);

  if (runEnded) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-app text-text-primary px-6 text-center gap-4">
        <p className="text-lg text-text-secondary">This game has already ended.</p>
        <Button
          type="button"
          onClick={() => navigate("/memorial")}
          className="h-auto bg-btn hover:bg-btn-hover active:bg-btn-pressed px-6 py-3 text-xs text-btn-text"
        >
          Go to Memorial
        </Button>
      </div>
    );
  }

  if (!gameState || !cat) {
    if (error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-app text-text-primary px-6 text-center gap-4">
          <p role="alert" className="text-hp">{error}</p>
          <Button
            type="button"
            onClick={() => runId && startBattle(runId)}
            className="h-auto bg-btn hover:bg-btn-hover active:bg-btn-pressed px-6 py-3 text-xs text-btn-text"
          >
            Try Again
          </Button>
        </div>
      );
    }
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-app text-text-primary gap-4">
        <PixelSpinner />
        <p role="status" className="retro text-xs text-text-secondary">
          Loading...
        </p>
      </div>
    );
  }

  if (gameOver) {
    return (
      <FarewellScreen
        catName={cat.name}
        onGoToMemorial={() => navigate("/memorial")}
      />
    );
  }

  const isPlayerTurn = gameState.phase === Phase.PLAYER_TURN;
  const canAct = isPlayerTurn && !isLoading;

  const latestEvent = events.length > 0 ? events[events.length - 1] : null;
  const statusText = error
    ? error
    : isLoading
    ? "Resolving turn..."
    : latestEvent ?? "Your turn!";

  const playerStatPanel = getPlayerStatFields(cat);
  const enemyStatPanel = getEnemyStatFields(gameState.enemy);
  const enemyAbilityList = toEnemyAbilityList(gameState.enemy);
  const enemyAbilityFieldsById = Object.fromEntries(
    gameState.enemy.abilities.map((a) => [a.id, getEnemyAbilityInfoFields(a)]),
  );

  return (
    <BattleArena
      player={{
        name: cat.name,
        avatarUrl: cat.avatar_url,
        classType: cat.class,
        hp: gameState.player_hp,
        maxHp: gameState.player_max_hp,
        mana: gameState.player_mana,
        maxMana: gameState.player_max_mana,
        isDefending: gameState.player_is_defending,
        shield: gameState.player_shield,
        lives: gameState.lives_remaining,
        statPanel: playerStatPanel,
      }}
      enemy={{
        name: gameState.enemy.name,
        avatarUrl: getEnemySpriteUrl(gameState.enemy.name),
        classType: Class.STRENGTH,
        hp: gameState.enemy.hp,
        maxHp: gameState.enemy.max_hp,
        mana: gameState.enemy.mana,
        maxMana: gameState.enemy.max_mana,
        shield: gameState.enemy.shield,
        statPanel: enemyStatPanel,
        abilityList: enemyAbilityList,
        abilityFieldsById: enemyAbilityFieldsById,
        pinnable: true,
      }}
      phase={gameState.phase}
      currentRound={gameState.current_round}
      statusText={statusText}
      isResolving={isLoading}
    >
      <AnimatePresence>
        {revival && (
          <motion.div
            key="revival-banner"
            initial={{ opacity: 0, scale: 0.85, y: -12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.85, y: -12 }}
            transition={{ type: "spring", stiffness: 320, damping: 22 }}
            className="mb-3 rounded-lg bg-accent/25 border-2 border-accent px-4 py-3 text-center text-sm font-medium text-text-primary shadow-lg shadow-accent/20"
          >
            <motion.span
              className="inline-block mr-1"
              animate={{ rotate: [0, -12, 12, 0], scale: [1, 1.3, 1] }}
              transition={{ duration: 0.8, repeat: Infinity, repeatDelay: 0.6 }}
            >
              {"\u2728"}
            </motion.span>
            A life was lost — {cat.name} has been revived!
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dismissible victory popup shown when a round is won. Dismissing it
          routes to the Overworld hub. Interactive modal (dimmed backdrop). */}
      <AnimatePresence>
        {victoryRound != null && (
          <motion.div
            key={`victory-${victoryRound}`}
            role="dialog"
            aria-modal="true"
            aria-label="Battle won"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="retro flex flex-col items-center gap-4 rounded-lg border-2 border-ultimate bg-panel px-8 py-6 text-center text-ultimate shadow-xl"
              initial={{ scale: 0.5, y: 20 }}
              animate={{ scale: [0.5, 1.15, 1], y: 0 }}
              exit={{ scale: 0.7, opacity: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            >
              <div className="text-2xl font-bold">{"\uD83C\uDF89"}</div>
              <div className="text-sm">Enemy defeated!</div>
              <div className="text-[10px] text-text-secondary">
                Round {victoryRound} reached.
              </div>
              <Button
                type="button"
                onClick={handleVictoryDismiss}
                className="mt-1 h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-[10px] text-app"
              >
                Continue
              </Button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <ActionButtons
        abilities={cat.abilities}
        cooldowns={gameState.player_ability_cooldowns}
        mana={gameState.player_mana}
        onAttack={handleAttack}
        onDefend={handleDefend}
        onUseAbility={handleAbility}
        disabled={!canAct}
      />
    </BattleArena>
  );
}

export default BattlePage;
