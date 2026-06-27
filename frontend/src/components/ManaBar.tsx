import { motion } from "framer-motion";

interface ManaBarProps {
  current: number;
  max: number;
}

function ManaBar({ current, max }: ManaBarProps) {
  const ratio = Math.max(0, Math.min(1, current / max));

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-gray-400 mb-0.5">
        <span>MP</span>
        <span>{current}/{max}</span>
      </div>
      <div className="w-full h-2.5 bg-gray-700 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-blue-500"
          animate={{ width: `${ratio * 100}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default ManaBar;
