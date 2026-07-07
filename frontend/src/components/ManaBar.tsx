import { motion } from "framer-motion";
import { Progress } from "@/components/ui/8bit/progress";

interface ManaBarProps {
  current: number;
  max: number;
}

function ManaBar({ current, max }: ManaBarProps) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, current / max)) : 0;

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-text-secondary mb-1">
        <span>MP</span>
        <motion.span
          key={current}
          initial={{ scale: 1 }}
          animate={{ scale: [1.2, 1] }}
          transition={{ duration: 0.25 }}
        >
          {current}/{max}
        </motion.span>
      </div>
      <Progress
        variant="retro"
        value={ratio * 100}
        progressBg="bg-mana"
        className="h-2.5"
      />
    </div>
  );
}

export default ManaBar;
