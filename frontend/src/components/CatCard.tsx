import { memo, useEffect, useRef } from "react";
import { motion, useAnimationControls } from "framer-motion";
import type { Class } from "../types/game";
import HealthBar from "./HealthBar";
import ManaBar from "./ManaBar";
import { Card } from "@/components/ui/8bit/card";

interface CatCardProps {
  name: string;
  avatarUrl?: string;
  classType: Class;
  hp: number;
  maxHp: number;
  mana: number;
  maxMana: number;
  isDefending?: boolean;
  shield?: number;
  flip?: boolean;
}

const classColors: Record<Class, string> = {
  STRENGTH: "text-class-strength",
  AGILITY: "text-class-agility",
  INTELLIGENCE: "text-class-intelligence",
};

function CatCard({
  name,
  classType,
  hp,
  maxHp,
  mana,
  maxMana,
  isDefending,
  shield,
  flip,
}: CatCardProps) {
  // React to HP changes with a short shake + flash so taking damage (or being
  // healed) reads clearly. Purely presentational — no effect on data flow.
  const controls = useAnimationControls();
  const prevHp = useRef(hp);

  useEffect(() => {
    const prev = prevHp.current;
    if (hp < prev) {
      controls.start({
        x: [0, -8, 8, -6, 6, -3, 0],
        filter: [
          "brightness(1)",
          "brightness(1.9)",
          "brightness(1)",
        ],
        transition: { duration: 0.45 },
      });
    } else if (hp > prev) {
      controls.start({
        filter: [
          "brightness(1)",
          "brightness(1.4) sepia(0.4) hue-rotate(60deg)",
          "brightness(1)",
        ],
        transition: { duration: 0.5 },
      });
    }
    prevHp.current = hp;
  }, [hp, controls]);

  return (
    <motion.div animate={controls}>
      <Card font="normal" className="bg-panel/60 border-border-ui text-text-primary">
        <div
          className={`flex items-center gap-4 p-4 ${
            flip ? "flex-row-reverse" : ""
          }`}
        >
          <div className="w-20 h-20 rounded-full bg-elevated flex items-center justify-center text-3xl shrink-0 border-2 border-border-ui">
            {"\uD83D\uDC31"}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className={`flex items-center gap-2 mb-1 ${
                flip ? "justify-end" : ""
              }`}
            >
              <span className="font-semibold text-text-primary truncate">{name}</span>
              <span className={`text-xs font-medium ${classColors[classType]}`}>
                {classType}
              </span>
            </div>
            <div className="space-y-1.5">
              <HealthBar current={hp} max={maxHp} />
              <ManaBar current={mana} max={maxMana} />
            </div>
            <div className={`flex gap-2 mt-1 ${flip ? "justify-end" : ""}`}>
              {isDefending && (
                <span className="text-xs text-defend font-medium">
                  {"\uD83D\uDEE1\uFE0F"} Defending
                </span>
              )}
              {shield !== undefined && shield > 0 && (
                <span className="text-xs text-shield font-medium">
                  {"\uD83D\uDEE1\uFE0F"} Shield {shield}
                </span>
              )}
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

export default memo(CatCard);
