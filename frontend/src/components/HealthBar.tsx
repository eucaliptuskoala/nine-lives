import { memo, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Progress } from "@/components/ui/8bit/progress";

interface HealthBarProps {
  current: number;
  max: number;
  color?: string;
}

function HealthBar({ current, max, color = "bg-red-500" }: HealthBarProps) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, current / max)) : 0;

  // Track the previous value so we can flash the bar when it changes: red-ish
  // for damage, green-ish for healing. Purely presentational feedback.
  const prevRef = useRef(current);
  const [flash, setFlash] = useState<"none" | "down" | "up">("none");

  useEffect(() => {
    const prev = prevRef.current;
    if (current < prev) setFlash("down");
    else if (current > prev) setFlash("up");
    prevRef.current = current;
  }, [current]);

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>HP</span>
        <motion.span
          key={current}
          initial={{ scale: 1 }}
          animate={{ scale: [1.25, 1] }}
          transition={{ duration: 0.25 }}
        >
          {current}/{max}
        </motion.span>
      </div>
      <div className="relative">
        <Progress
          variant="retro"
          value={ratio * 100}
          progressBg={color}
          className="h-3"
        />
        <AnimatePresence>
          {flash !== "none" && (
            <motion.div
              key={`flash-${flash}-${current}`}
              aria-hidden="true"
              className={`pointer-events-none absolute inset-0 ${
                flash === "down" ? "bg-red-400" : "bg-green-400"
              }`}
              initial={{ opacity: 0.55 }}
              animate={{ opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
              onAnimationComplete={() => setFlash("none")}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default memo(HealthBar);
