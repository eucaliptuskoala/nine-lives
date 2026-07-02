import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Phase } from "../types/game";
import { useGameState } from "../hooks/useGameState";
import BattleArena from "../components/BattleArena";
import ActionButtons from "../components/ActionButtons";
import FarewellScreen from "../components/FarewellScreen";

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

  // Kick off (or resume) the battle on mount. `start` is idempotent on the
  // backend, so a page refresh restores the persisted state.
  useEffect(() => {
    if (runId) {
      startBattle(runId);
    }
  }, [runId, startBattle]);

  // The backend is the source of truth for game-over; navigate to the memorial
  // once it reports the run has ended.
  useEffect(() => {
    if (gameOver) {
      navigate("/memorial");
    }
  }, [gameOver, navigate]);

  // Session expired mid-battle (401): the hook has already persisted the run to
  // session storage. Redirect to login, passing the battle path so LoginPage's
  // post-login redirect returns the user to their battle.
  useEffect(() => {
    if (sessionExpired) {
      navigate("/login", { state: { from: `/battle/${runId}` } });
    }
  }, [sessionExpired, navigate, runId]);

  // Run already ended (409): the spec says to OFFER navigation rather than
  // auto-redirect, so show a clear message with a button to the memorial.
  if (runEnded) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white px-6 text-center gap-4">
        <p className="text-lg text-gray-200">This game has already ended.</p>
        <button
          onClick={() => navigate("/memorial")}
          className="px-6 py-3 rounded-lg bg-purple-700 hover:bg-purple-600 font-medium transition-colors"
        >
          Go to Memorial
        </button>
      </div>
    );
  }

  // Loading state: no state yet and no error to show.
  if (!gameState || !cat) {
    if (error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white px-6 text-center gap-4">
          <p className="text-red-400">{error}</p>
          <button
            onClick={() => runId && startBattle(runId)}
            className="px-6 py-3 rounded-lg bg-gray-700 hover:bg-gray-600 font-medium transition-colors"
          >
            Try Again
          </button>
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900 text-white">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  // Game over is handled via navigation; render a farewell in the meantime.
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

  // Derive the status/turn-log text from the events returned by the API, with
  // sensible fallbacks for loading and idle states.
  const latestEvent = events.length > 0 ? events[events.length - 1] : null;
  const statusText = error
    ? error
    : isLoading
    ? "Resolving turn..."
    : latestEvent ?? "Your turn!";

  return (
    <BattleArena
      player={{
        name: cat.name,
        classType: cat.class,
        hp: gameState.player_hp,
        maxHp: gameState.player_max_hp,
        mana: gameState.player_mana,
        maxMana: gameState.player_max_mana,
        isDefending: gameState.player_is_defending,
        shield: gameState.player_shield,
        lives: gameState.lives_remaining,
      }}
      enemy={{
        name: gameState.enemy.name,
        classType: "STRENGTH",
        hp: gameState.enemy.hp,
        maxHp: gameState.enemy.max_hp,
        mana: gameState.enemy.mana,
        maxMana: gameState.enemy.max_mana,
        shield: gameState.enemy.shield,
      }}
      phase={gameState.phase}
      currentRound={gameState.current_round}
      statusText={statusText}
    >
      {revival && (
        <div className="mb-3 rounded-lg bg-purple-900/60 border border-purple-500 px-4 py-2 text-center text-sm text-purple-100">
          {"\u2728"} A life was lost — {cat.name} has been revived!
        </div>
      )}
      <ActionButtons
        abilities={cat.abilities}
        cooldowns={gameState.player_ability_cooldowns}
        mana={gameState.player_mana}
        onAttack={() => submitAction("attack")}
        onDefend={() => submitAction("defend")}
        onUseAbility={(abilityId) => submitAction("ability", abilityId)}
        disabled={!canAct}
      />
    </BattleArena>
  );
}

export default BattlePage;
